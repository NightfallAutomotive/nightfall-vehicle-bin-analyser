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


PROFILES = (
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
        match_terms=("mev1746", "mev17.4.6", "n20", "184hp"),
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
        hits = [t for t in p.match_terms if _norm(t) in haystack]
        if hits:
            scored.append((len(hits), p))
    if not scored:
        return {"key":"generic", "label":"Generic BIN analysis", "family":"unknown", "confidence":0, "profile":None}
    scored.sort(key=lambda x:x[0], reverse=True)
    count, p = scored[0]
    confidence = min(100, 45 + count * 20)
    return {"key":p.key, "label":p.label, "family":p.family, "confidence":confidence, "profile":asdict(p)}
