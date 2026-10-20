from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
import re


@dataclass(frozen=True)
class CalibrationDefinition:
    name: str
    purpose: str
    units: str
    axis_notes: str
    role: str
    include_terms: tuple[str, ...] = ()
    exclude_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class ECUProfile:
    key: str
    label: str
    family: str
    match_terms: tuple[str, ...]
    primary: tuple[CalibrationDefinition, ...]
    secondary: tuple[CalibrationDefinition, ...]
    exclusions: tuple[str, ...]
    notes: str
    # False for pre-torque-model ECUs, which have no torque limiter to graph.
    torque_model: bool = True


PROFILES = (
    ECUProfile(
        key="marelli_iaw",
        label="Magneti Marelli IAW",
        family="Magneti Marelli IAW",
        match_terms=("marelli", "iaw"),
        primary=(),
        secondary=(),
        exclusions=(),
        notes=(
            "Early-2000s petrol ECU without a torque model. Tunes change "
            "fuelling, ignition and load tables, so there is no torque "
            "limiter to graph."
        ),
        torque_model=False,
    ),
    ECUProfile(
        key="dcm6_2",
        label="Delphi DCM6.2",
        family="Delphi DCM6.2",
        match_terms=("dcm6.2", "dcm6_2", "delphi", "04l906056a"),
        primary=(CalibrationDefinition(
            name="T_D_PT_CRNK_TORQ_MAX_APM",
            purpose="Maximum permitted crank torque",
            units="Nm",
            axis_notes="Damos describes the map as a 2D torque map against selected engine temperature.",
            role="primary_torque_limit",
            include_terms=("maximum permitted crank torque", "crnk_torq_max"),
        ),),
        secondary=(CalibrationDefinition(
            name="T_D_PT_CRNK_TORQ_RAMPUP_LIM_APM",
            purpose="Maximum ramp-up limit for added crank torque",
            units="Nm/s",
            axis_notes="Temperature-related torque-rate map.",
            role="exclude_from_torque_limiter",
            exclude_terms=("rampup", "ramp-up", "nm/s"),
        ),),
        exclusions=("rampup", "ramp-up", "nm/s"),
        notes="Do not assume the 2D map is RPM x torque. The Damos identifies selected engine temperature as the map axis context.",
    ),
    ECUProfile(
        key="edc17cp14",
        label="Bosch EDC17CP14",
        family="Bosch EDC17CP14",
        match_terms=("edc17cp14", "seat leon", "leon fr"),
        primary=(CalibrationDefinition(
            name="r Maximaldrehmomentbegrenzung",
            purpose="Maximum torque limitation",
            units="Nm / Damos-defined torque units",
            axis_notes="Use the Damos axis/scaling definition when available; do not assume 0.1 globally.",
            role="primary_torque_limit",
            include_terms=("maximaldrehmomentbegrenzung",),
        ),),
        secondary=(CalibrationDefinition(
            name="r Minimumdrehmomentbegrenzung",
            purpose="Minimum torque limitation",
            units="Damos-defined torque units",
            axis_notes="Related torque-management calibration, not the primary maximum limiter.",
            role="secondary_torque_limit",
        ),),
        exclusions=(),
        notes="The Damos contains many torque-management functions. Prefer the documented maximum-torque limitation definition over generic torque maps.",
    ),
    ECUProfile(
        key="edc15",
        label="Bosch EDC15",
        family="Bosch EDC15",
        match_terms=("edc15", "edc15c2", "edc15c3", "edc15c4", "edc15p", "edc15v", "edc15vm"),
        primary=(CalibrationDefinition(
            name="mrwBDBN_KL",
            purpose="Full-load injection quantity limit over engine speed",
            units="mm3/stroke (raw / 100)",
            axis_notes="Curve [source address, n, rpm axis, values], little-endian; engine speed raw = rpm.",
            role="primary_quantity_limit",
        ),),
        secondary=(CalibrationDefinition(
            name="mrwBRA_KF",
            purpose="Smoke limiter: injection quantity over engine speed and air mass",
            units="mm3/stroke (raw / 100)",
            axis_notes="Map with the same axis headers.",
            role="secondary_quantity_limit",
        ),),
        exclusions=(),
        notes="EDC15 has no torque model; output is limited by injection quantity. Layout and scaling from the BMW EDC15C A2L.",
    ),
    ECUProfile(
        key="edc16",
        label="Bosch EDC16 (VAG)",
        family="Bosch EDC16",
        match_terms=("edc16", "edc16u1", "edc16u31", "edc16u34", "edc16cp34"),
        primary=(CalibrationDefinition(
            name="EngPrt_trqLimP_MAP",
            purpose="Engine-protection torque limit over ambient pressure and engine speed",
            units="Nm (raw / 10)",
            axis_notes="Inline Kf_Xs16_Ys16_Ws16, big-endian: ambient pressure (hPa) x engine speed (raw = rpm).",
            role="primary_torque_limit",
            include_terms=("trqlimp_map",),
        ),),
        secondary=(CalibrationDefinition(
            name="EngPrt_trqNLim_CUR",
            purpose="Engine-speed limit expressed as a torque limit",
            units="Nm (raw / 10)",
            axis_notes="Where a hard rev cut is usually set.",
            role="secondary_torque_limit",
        ),),
        exclusions=(),
        notes="Layout and scaling from the VAG EDC16U R5 TDI A2L. Map addresses vary by software version, so maps are found from their inline headers.",
    ),
    ECUProfile(
        key="edc17c64",
        label="Bosch EDC17C64",
        family="Bosch EDC17C64",
        match_terms=("edc17c64",),
        primary=(CalibrationDefinition(
            name="EngPrt_trqLimP_MAP",
            purpose="Engine-protection torque limit over ambient pressure and engine speed",
            units="Nm (raw / 10)",
            axis_notes="Inline Map_Xs16Ys16Ws16: ambient pressure (hPa) x engine speed (raw / 2 = rpm).",
            role="primary_torque_limit",
            include_terms=("trqlimp_map",),
        ),),
        secondary=(CalibrationDefinition(
            name="EngPrt_trqLimPBoost_MAP",
            purpose="Engine-protection torque limit with boost active",
            units="Nm (raw / 10)",
            axis_notes="Same layout as EngPrt_trqLimP_MAP.",
            role="secondary_torque_limit",
        ),),
        exclusions=(),
        notes="Layout and scaling taken from the VAG EDC17C46 2.0 TDI A2L, which shares this map with EDC17C64.",
    ),
    ECUProfile(
        key="edc17cp55",
        label="Bosch EDC17CP55 (JLR)",
        family="Bosch EDC17CP55",
        match_terms=("edc17cp55",),
        primary=(CalibrationDefinition(
            name="Engine torque limit curve",
            purpose="Maximum engine torque over engine speed",
            units="Nm (raw / 10)",
            axis_notes="Inline Kl_Xs16Ws16 curve; engine speed raw / 2 = rpm. No A2L available, layout inferred from the BIN.",
            role="primary_torque_limit_candidate",
        ),),
        secondary=(CalibrationDefinition(
            name="Per-gear torque limit curves",
            purpose="Torque limits repeated once per gear",
            units="Nm (raw / 10)",
            axis_notes="Identical inline curves, one per gear.",
            role="secondary_torque_limit",
        ),),
        exclusions=(),
        notes="Stage 1 files commonly remove the pressure and temperature limiters by setting them to 1000 Nm.",
    ),
    ECUProfile(
        key="edc17c41",
        label="Bosch EDC17C41",
        family="Bosch EDC17C41",
        match_terms=("edc17c41", "523211", "318d"),
        primary=(CalibrationDefinition(
            name="ACCtl_trqTEngLim_MAP",
            purpose="Engine torque limitation map candidate",
            units="Damos-defined torque units",
            axis_notes="Validate axes and operating context against the Damos before promotion to primary.",
            role="primary_torque_limit_candidate",
            include_terms=("trqTEngLim_MAP", "torque limitation"),
        ),),
        secondary=(CalibrationDefinition(
            name="AccMon_trqMaxEng_C",
            purpose="Acceleration-monitoring maximum engine torque",
            units="Damos-defined torque units",
            axis_notes="Acceleration-monitoring function; not automatically the main torque limiter.",
            role="secondary_torque_limit",
        ),
        CalibrationDefinition(
            name="AGSDem_trqLimMax_C",
            purpose="AGSDem maximum limiting torque",
            units="Damos-defined torque units",
            axis_notes="Powertrain request/limiting function.",
            role="secondary_torque_limit",
        )),
        exclusions=(),
        notes="BMW EDC17C41 contains several torque limits with different purposes. Semantic identity must outrank numerical similarity.",
    ),
    ECUProfile(
        key="edc17cp45_bmw",
        label="BMW EDC17CP45",
        family="BMW EDC17CP45",
        match_terms=("f10", "f11", "f18", "523206", "edc17cp45"),
        primary=(CalibrationDefinition(
            name="MoXTrqLim_Eng / MoFTrqLim_Eng",
            purpose="Engine torque limitation family",
            units="Damos-defined torque units",
            axis_notes="Use the Damos-defined axes and operating conditions.",
            role="primary_torque_limit_candidate",
            include_terms=("moxtrqlim_eng", "moftrqlim_eng", "drehmomentbegrenzung"),
        ),),
        secondary=(CalibrationDefinition(
            name="Acceleration / transmission / vehicle torque limits",
            purpose="Other torque-management limits",
            units="Damos-defined",
            axis_notes="Do not automatically classify these as the main engine torque limiter.",
            role="secondary_torque_limit",
        ),),
        exclusions=("acceleration monitoring", "climate", "steering", "transmission"),
        notes="The Damos contains many torque-related limits; context is required to identify the main engine limiter.",
    ),
    ECUProfile(
        key="mev1746_n20",
        label="BMW N20 MEV17.4.6",
        family="BMW MEV17.4.6",
        match_terms=("mev1746", "mev17.4.6", "n20", "n20b20", "184hp"),
        primary=(CalibrationDefinition(
            name="maximales Maschinendrehmoment",
            purpose="Maximum machine/engine torque",
            units="Damos-defined torque units",
            axis_notes="Validate temperature/air-path/operating-state dependencies from the Damos.",
            role="primary_torque_limit_candidate",
            include_terms=("maximales maschinendrehmoment",),
        ),),
        secondary=(CalibrationDefinition(
            name="Torque limits over engine temperature",
            purpose="Temperature-dependent torque limits",
            units="Damos-defined torque units",
            axis_notes="Air-path and ignition-path limits may be separate functions.",
            role="secondary_torque_limit",
        ),),
        exclusions=("reserve", "diagnose", "climate", "wandler", "converter"),
        notes="MEV17.4.6 has multiple torque-management paths. Avoid treating any temperature/air-path correction as the primary limiter without context.",
    ),
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def identify_profile(*names: Optional[str]) -> dict:
    haystack = _norm(" ".join(n or "" for n in names))
    scored = []
    for p in PROFILES:
        # Match whole words only, so "f10" doesn't match "f100" and "n20"
        # doesn't match "n2000".
        hits = [t for t in p.match_terms if f" {_norm(t)} " in f" {haystack} "]
        if hits:
            scored.append((len(hits), p))
    if not scored:
        return {"key":"generic", "label":"Generic BIN analysis", "family":"unknown", "confidence":0, "profile":None}
    scored.sort(key=lambda x:x[0], reverse=True)
    count, p = scored[0]
    confidence = min(100, 45 + count * 20)
    return {"key":p.key, "label":p.label, "family":p.family, "confidence":confidence, "profile":asdict(p)}
