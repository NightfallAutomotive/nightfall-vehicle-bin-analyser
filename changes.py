"""Describe what a modified ECU file changed: fault checks switched off,
speed limits raised, switches flipped, and anything else.

A comparison needs the original. When only one file is uploaded, the
original is looked up in a library of stock files by Bosch software number
(see ``OriLibrary``); without a match, only ``pattern_checks`` run, which can
say much less.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import threading
from collections import Counter
from pathlib import Path

from analyzer import changed_regions, find_bosch_limiters

# Bosch software numbers ("1037" + 6 digits). A modified file keeps the
# number of the original it was made from.
SOFTWARE_ID_RE = re.compile(rb"1037\d{6}")

# Bosch EDC17 fault handling keeps one entry per fault check (DFC) in several
# parallel tables (names from the VAG EDC17C46 A2L):
#   DFC_DisblMsk  u16  disable mask; 0xFFFF switches the check off
#   DFES_Cls      u8   fault class (0-15); 0 means it never stores a code
#   DTC table     u16  the fault code each check reports
FAULT_MASK_OFF = 0xFFFF
FAULT_CLASS_MAX = 15

# Speed limits are stored in 0.01 km/h (BMW) or 1/128 km/h (VAG). A tune that
# removes the limiter sets several of them to one common, much higher value.
SPEED_SCALES = (0.01, 1 / 128)
SPEED_STOCK_KMH = (150, 270)
SPEED_RAISED_KMH = (280, 500)
SPEED_MIN_RUN = 3
# Real limits are whole km/h and a tune sets them to a round figure; flat
# stretches of a tuned map don't follow that, and give many different values.
SPEED_ROUND_TO = 5
SPEED_MAX_DISTINCT = 2
# Without the class cross-check, fewer changed masks than this are noise
FAULT_MIN_UNVERIFIED = 10

DEFAULT_LIBRARY = Path(__file__).parent / "library"


def software_ids(data):
    """Return the Bosch software numbers found in a file, most common first."""
    counts = Counter(m.decode() for m in SOFTWARE_ID_RE.findall(data))
    return [sw for sw, _ in counts.most_common()]


# ---------- Fault checks ----------

def _small_byte_table(data, off, radius=8):
    """True if the bytes around off all look like fault classes."""
    lo, hi = max(0, off - radius), min(len(data), off + radius + 1)
    return all(b <= FAULT_CLASS_MAX for b in data[lo:hi])


def _bmw_fault_codes(ori, masks, classes, shift):
    """Read the fault codes for the disabled checks from the BMW EDC17 layout.

    There, the u16 code table follows the disable-mask table directly, both
    N entries long, and entry 0 is the unused check (mask 0xFFFF, class 1,
    code 0 or 1). Returns a list of codes, or None unless exactly one table
    length fits all of that.
    """
    if not masks or len(masks) != len(classes):
        return None
    word = lambda off: struct.unpack_from("<H", ori, off)[0]
    first = min(masks)
    # class_offset = mask_offset / 2 + shift for the same check
    candidates = []
    for start in range(first, max(0, first - 2 * 8000), -2):
        if word(start) != FAULT_MASK_OFF:
            continue
        cls_start = start // 2 + shift
        if not (0 <= cls_start < len(ori)) or ori[cls_start] != 1:
            continue
        # The class table is a run of small bytes; its end bounds N
        run_end = cls_start
        while run_end < len(ori) and ori[run_end] <= FAULT_CLASS_MAX:
            run_end += 1
        for n in range(run_end - cls_start - 4, run_end - cls_start + 1):
            if n <= 0 or start + 2 * n <= max(masks):
                continue
            codes_start = start + 2 * n
            if codes_start + 2 * n > len(ori):
                continue
            if word(codes_start) in (0, 1) and word(codes_start + 2) > 1:
                candidates.append((start, n, codes_start))
        if candidates:
            break
    if len(candidates) != 1:
        return None
    start, n, codes_start = candidates[0]
    # Several checks can report the same code; list each code once
    counts = Counter()
    for off in sorted(masks):
        code = word(codes_start + (off - start))
        if code > 1:
            counts[f"{code:04X}"] += 1
    codes = [{"code": c, "checks": k} for c, k in sorted(counts.items())]
    return {"codes": codes, "format": "bmw", "fault_checks_total": n}


def fault_changes(ori, mod):
    """Find fault checks switched off between ori and mod."""
    n = min(len(ori), len(mod)) // 2
    masks = []
    for region in changed_regions(ori, mod):
        start = region["offset"] & ~1
        end = region["offset"] + region["length"]
        for off in range(start, end, 2):
            if off // 2 >= n:
                break
            old = struct.unpack_from("<H", ori, off)[0]
            new = struct.unpack_from("<H", mod, off)[0]
            if new == FAULT_MASK_OFF and old != FAULT_MASK_OFF:
                masks.append(off)
    classes = [
        off for region in changed_regions(ori, mod)
        for off in range(region["offset"], region["offset"] + region["length"])
        if mod[off] == 0 and 0 < ori[off] <= FAULT_CLASS_MAX
        and _small_byte_table(ori, off)
    ]

    # The same checks are switched off in both tables, so every disabled mask
    # should line up with a cleared class at one shift. Other small bytes the
    # tune changed don't line up and are left out.
    verified = False
    shift = None
    aligned = []
    if masks and classes:
        diffs = Counter(c - m // 2 for m in masks for c in classes)
        shift, hits = diffs.most_common(1)[0]
        verified = hits == len(masks)
        if verified:
            aligned = [m // 2 + shift for m in masks]

    result = {
        "disabled_masks": len(masks),
        "cleared_classes": len(classes),
        "fault_checks_off": len(masks) if verified else max(len(masks), len(classes)),
        "verified": verified,
        "codes": [],
        "code_format": None,
        # Bytes and words that belong to the fault tables
        "offsets": sorted(set(masks) | {m + 1 for m in masks} | set(aligned or classes)),
    }
    if verified:
        found = _bmw_fault_codes(ori, masks, aligned, shift)
        if found:
            result["codes"] = found["codes"]
            result["code_format"] = found["format"]
            result["fault_checks_total"] = found["fault_checks_total"]
    return result


# ---------- Speed limits ----------

def _whole_kmh(raw, scale, step=1):
    kmh = raw * scale
    return abs(kmh - round(kmh)) < 1e-6 and round(kmh) % step == 0


def _speed_runs(words_old, words_new, scale, need_old=True):
    """Runs of at least SPEED_MIN_RUN neighbouring limits set to one raised,
    round value."""
    runs = []
    i, n = 0, len(words_new)
    lo_raised, hi_raised = (v / scale for v in SPEED_RAISED_KMH)
    lo_stock, hi_stock = (v / scale for v in SPEED_STOCK_KMH)
    while i < n:
        new = words_new[i]
        if (not lo_raised <= new <= hi_raised or not _whole_kmh(new, scale, SPEED_ROUND_TO)
                or (need_old and words_old[i] == new)):
            i += 1
            continue
        j = i
        while (j + 1 < n and words_new[j + 1] == new
               and (not need_old or words_old[j + 1] != new)):
            j += 1
        olds = words_old[i:j + 1] if need_old else []
        if j - i + 1 >= SPEED_MIN_RUN and (not need_old or all(
                lo_stock * 0.7 <= v <= hi_stock and _whole_kmh(v, scale) for v in olds)):
            runs.append((i, j - i + 1, olds, new))
        i = j + 1
    return runs


def speed_limit_changes(ori, mod):
    out = []
    for region in changed_regions(ori, mod, gap=64):
        start = max(0, (region["offset"] & ~1) - 2 * SPEED_MIN_RUN)
        end = min(len(ori), region["offset"] + region["length"] + 2 * SPEED_MIN_RUN)
        end -= (end - start) % 2
        count = (end - start) // 2
        old = struct.unpack_from(f"<{count}H", ori, start)
        new = struct.unpack_from(f"<{count}H", mod, start)
        for scale in SPEED_SCALES:
            for i, length, olds, value in _speed_runs(old, new, scale):
                out.append({
                    "offset": start + 2 * i,
                    "count": length,
                    "old_kmh": sorted({round(v * scale) for v in olds}),
                    "new_kmh": round(value * scale),
                })
    if len({s["new_kmh"] for s in out}) > SPEED_MAX_DISTINCT:
        return []
    return out


# ---------- Switches and the rest ----------

def switch_changes(ori, mod, exclude):
    """Bytes flipped between 0 and 1 (feature on/off switches).

    Only areas where every change is such a flip count; a 0 -> 1 step inside
    a tuned map is not a switch.
    """
    out = []
    for region in changed_regions(ori, mod, gap=8):
        offs = [
            off for off in range(region["offset"], region["offset"] + region["length"])
            if ori[off] != mod[off] and off not in exclude
        ]
        if offs and all({ori[off], mod[off]} == {0, 1} for off in offs):
            out.extend({"offset": off, "old": ori[off], "new": mod[off]} for off in offs)
    return out


def describe_changes(ori, mod):
    """Summarise every change between an original and a modified file."""
    if len(ori) != len(mod):
        raise ValueError("Original and modified BIN sizes must match.")
    regions = changed_regions(ori, mod)
    faults = fault_changes(ori, mod)
    speeds = speed_limit_changes(ori, mod)

    explained = set(faults["offsets"])
    for s in speeds:
        explained.update(range(s["offset"], s["offset"] + 2 * s["count"]))
    switches = switch_changes(ori, mod, explained)

    summary = []
    if faults["verified"]:
        text = f"{faults['fault_checks_off']} fault checks switched off"
        if faults["codes"]:
            text += f" ({len(faults['codes'])} different fault codes)"
        summary.append(text)
    elif max(faults["disabled_masks"], faults["cleared_classes"]) >= FAULT_MIN_UNVERIFIED:
        summary.append(
            f"Fault checks switched off: {faults['disabled_masks']} checks disabled "
            f"and {faults['cleared_classes']} fault classes cleared"
        )
    # One line per new top speed, however the limits are split up
    by_speed = {}
    for s in speeds:
        group = by_speed.setdefault(s["new_kmh"], {"count": 0, "old": set()})
        group["count"] += s["count"]
        group["old"].update(s["old_kmh"])
    for new, group in sorted(by_speed.items()):
        olds = sorted(group["old"])
        was = f"{olds[0]}" if len(olds) == 1 else f"{olds[0]}–{olds[-1]}"
        summary.append(
            f"Speed limiter raised: {group['count']} limits from {was} km/h to {new} km/h"
        )
    if switches:
        summary.append(f"{len(switches)} on/off switches flipped")

    return {
        "changed_bytes": sum(r["length"] for r in regions),
        "changed_regions": len(regions),
        "summary": summary,
        "faults": faults,
        "speed_limits": speeds,
        "switches": switches,
    }


# ---------- Single file without an original ----------

def pattern_checks(data):
    """What can be said about a file with nothing to compare it against.

    Without the original there is no way to tell which fault checks or
    switches were changed, so this only reports the pressure x RPM torque
    limiters the file holds, and those that look switched off (a flat
    1000 Nm line). Lone RPM curves are too easily confused with other data
    to report without a comparison.
    """
    limiters = [lim for lim in find_bosch_limiters(data) if lim["kind"] == "map"]
    findings = []
    for lim in limiters[:4]:
        where = f"0x{lim['offset']:X}"
        copies = f" ({lim['copies']} identical copies)" if lim["copies"] > 1 else ""
        if lim["removed"]:
            findings.append(f"Torque limiter at {where} is switched off (set to 1000 Nm){copies}")
        else:
            findings.append(
                f"Torque limiter at {where}{copies} allows up to "
                f"{lim['peak_nm']:g} Nm (peak at {lim['peak_rpm']} RPM, "
                f"{lim['pressure_hpa']} hPa)"
            )
    if not findings:
        findings.append("No torque limiter map recognised in this file.")
    return {"findings": findings, "limiters": limiters}


# ---------- Library of stock originals ----------

class OriLibrary:
    """Stock original files on the server, looked up by software number.

    The folder comes from NIGHTFALL_ORI_LIBRARY (default: ./library). Files
    can be named anything; build_library.py fills it from a WinOLS database.
    Originals that people upload are saved in its "uploads" folder, and the
    curated files are preferred over them, since an uploaded "original" may
    have been tuned already.
    """

    MIN_SIZE = 256 * 1024
    MAX_SIZE = 16 * 1024 * 1024
    # Total room for saved uploads, so a public server's disk can't be
    # filled (NIGHTFALL_UPLOADS_MAX_GB, default 2)
    UPLOADS_MAX_BYTES = int(float(os.environ.get("NIGHTFALL_UPLOADS_MAX_GB", "2")) * 1024 ** 3)

    def __init__(self, folder=None):
        self.folder = Path(folder or os.environ.get("NIGHTFALL_ORI_LIBRARY") or DEFAULT_LIBRARY)
        self.uploads = self.folder / "uploads"
        self._index = None
        self._lock = threading.Lock()

    def _is_upload(self, path):
        return self.uploads in path.parents

    def _build(self):
        index = {}
        if self.folder.is_dir():
            for path in sorted(self.folder.rglob("*")):
                if not path.is_file() or path.stat().st_size < self.MIN_SIZE:
                    continue
                data = path.read_bytes()
                for sw in software_ids(data)[:3]:
                    index.setdefault(sw, []).append(path)
        self._index = index

    def find(self, data):
        """Return (path, software id, original bytes) for the closest stock
        file with the same software number and size, or None. Curated files
        win over uploaded ones."""
        with self._lock:
            if self._index is None:
                self._build()
            index = {sw: list(paths) for sw, paths in self._index.items()}
        best = None
        for sw in software_ids(data):
            for path in index.get(sw, []):
                ref = path.read_bytes()
                if len(ref) != len(data):
                    continue
                differing = sum(r["length"] for r in changed_regions(ref, data))
                rank = (self._is_upload(path), differing)
                if best is None or rank < best[0]:
                    best = (rank, path, sw, ref)
        if best is None:
            return None
        return best[1], best[2], best[3]

    def add(self, data):
        """Save an uploaded original. Only the contents are kept, named by
        software number and hash; the uploaded filename is not."""
        ids = software_ids(data)
        if not ids:
            return {"saved": False, "reason": "no Bosch software number in the file"}
        if not self.MIN_SIZE <= len(data) <= self.MAX_SIZE:
            return {"saved": False, "reason": "not a full flash read", "software": ids[0]}
        name = f"{ids[0]}_{file_hash(data)[:10]}.bin"
        with self._lock:
            if self._index is None:
                self._build()
            if any(p.name == name for paths in self._index.values() for p in paths):
                return {"saved": False, "reason": "already in the library", "software": ids[0]}
            used = sum(p.stat().st_size for p in self.uploads.glob("*.bin")) if self.uploads.is_dir() else 0
            if used + len(data) > self.UPLOADS_MAX_BYTES:
                return {"saved": False, "reason": "the library is full", "software": ids[0]}
            self.uploads.mkdir(parents=True, exist_ok=True)
            target = self.uploads / name
            # Write then rename, so a half-written file is never indexed
            partial = target.with_suffix(".part")
            partial.write_bytes(data)
            partial.replace(target)
            for sw in ids[:3]:
                self._index.setdefault(sw, []).append(target)
        return {"saved": True, "software": ids[0]}


def file_hash(data):
    return hashlib.sha1(data).hexdigest()


# ---------- Entry point for one uploaded file ----------

def analyse_single(data, name="", library=None):
    """Work out what was done to a file uploaded on its own.

    Compares it with the stock original for its software number when the
    library has one, and falls back to pattern checks otherwise.
    """
    from analyzer import ANALYSER_VERSION, analyse
    from calibration_definitions_v3 import identify_profile

    library = library or OriLibrary()
    ids = software_ids(data)
    match = library.find(data)

    if match:
        path, sw, ref = match
        comparison = {"mode": "library", "software": sw, "reference": path.name}
        if ref == data:
            return {
                "version": ANALYSER_VERSION,
                "profile": identify_profile(name),
                "ok": True,
                "map_type": "unchanged",
                "confidence": "n/a",
                "message": f"This file is identical to the stock original for software {sw}.",
                "comparison": comparison,
                "changes": describe_changes(ref, data),
                "candidates": [],
                "map_options": [],
            }
        result = analyse(ref, data, name, name)
        result["comparison"] = comparison
        result["changes"] = describe_changes(ref, data)
        return result

    software = ids[0] if ids else None
    return {
        "version": ANALYSER_VERSION,
        "profile": identify_profile(name),
        "ok": True,
        "map_type": "single_file",
        "confidence": "pattern checks",
        "message": (
            "No stock original for "
            + (f"software {software}" if software else "this file")
            + " is in the library, so only pattern checks could run. "
            "Upload the original as well to see everything that was changed."
        ),
        "comparison": {"mode": "pattern", "software": software},
        "patterns": pattern_checks(data),
        "candidates": [],
        "map_options": [],
    }
