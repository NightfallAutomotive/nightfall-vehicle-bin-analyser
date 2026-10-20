"""Fill the stock-original library used for single-file analysis.

Copies original reads out of a WinOLS job database (the "00 - ORI" and
"99 - BACKUP" folders) into the library, named by Bosch software number and
content hash, so no registration, VIN or customer name is carried over.

    python build_library.py "/path/to/WinOLS Database"
    python build_library.py "/path/to/WinOLS Database" --library /srv/library --dry-run

The library folder defaults to NIGHTFALL_ORI_LIBRARY, or ./library. Only
add reads you know are stock: a car that was tuned before it was read gives
a misleading "original".
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from changes import DEFAULT_LIBRARY, software_ids

ORIGINAL_FOLDERS = ("00 - ORI", "99 - BACKUP")
MIN_SIZE = 256 * 1024


def candidates(source):
    for path in sorted(Path(source).rglob("*.bin")):
        if not any(part in ORIGINAL_FOLDERS for part in path.parts):
            continue
        if "eeprom" in path.name.lower() or path.stat().st_size < MIN_SIZE:
            continue
        yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="WinOLS database folder to read originals from")
    parser.add_argument("--library", default=os.environ.get("NIGHTFALL_ORI_LIBRARY") or DEFAULT_LIBRARY,
                        help="library folder to copy into")
    parser.add_argument("--dry-run", action="store_true", help="list what would be copied")
    args = parser.parse_args()

    library = Path(args.library)
    if not args.dry_run:
        library.mkdir(parents=True, exist_ok=True)

    added = skipped = no_id = 0
    seen = set()
    for path in candidates(args.source):
        data = path.read_bytes()
        ids = software_ids(data)
        if not ids:
            no_id += 1
            continue
        target = library / f"{ids[0]}_{hashlib.sha1(data).hexdigest()[:10]}.bin"
        if target.exists() or target.name in seen:
            skipped += 1
            continue
        seen.add(target.name)
        print(f"{'would add' if args.dry_run else 'added'} {target.name}  ({len(data) // 1024} KB)")
        if not args.dry_run:
            target.write_bytes(data)
        added += 1

    print(f"\n{added} added, {skipped} already in the library, {no_id} without a software number")


if __name__ == "__main__":
    main()
