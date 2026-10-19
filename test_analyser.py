"""Analyser regression tests.

Run the tests with `python -m pytest`, or print a summary report for each
test BIN pair with `python test_analyser.py`.
"""
import struct
from functools import cache
from pathlib import Path

import pytest

from analyzer import (
    GRAPH_RPM_MAX,
    GRAPH_RPM_MIN,
    analyse,
    build_candidates,
    read_u16,
)
from calibration_definitions_v3 import identify_profile

base = Path(__file__).parent
test_files = base / "test-files"

pairs = [
    ("Seat Leon", test_files / "ori.bin", test_files / "stage1.bin"),
    ("Car 2", test_files / "car2_ori.bin", test_files / "car2_stage1.bin"),
    (
        "Seat EDC17C64",
        test_files / "edc17c64_ori.bin",
        test_files / "edc17c64_stage1.bin",
    ),
    # This car was already tuned when its "ORI" was read, so its 460 Nm
    # baseline is a previous tune, not stock.
    (
        "Seat Leon EDC17C64 #2",
        test_files / "edc17c64_leon2_ori.bin",
        test_files / "edc17c64_leon2_stage2.bin",
    ),
    (
        "VW Touareg EDC16U1",
        test_files / "edc16u1_ori.bin",
        test_files / "edc16u1_stage1.bin",
    ),
    (
        "Jaguar EDC17CP55",
        test_files / "edc17cp55_ori.bin",
        test_files / "edc17cp55_stage1.bin",
    ),
]


@cache
def result_for(name):
    _, ori_path, stage_path = next(p for p in pairs if p[0] == name)
    return analyse(
        ori_path.read_bytes(),
        stage_path.read_bytes(),
        ori_name=ori_path.name,
        stage_name=stage_path.name,
    )


def candidate_range(c):
    if c["layout"] in ("interleaved", "trailing_interleaved"):
        size = c["rows"] * (c["columns"] + 1) * 2
    else:
        size = c["rows"] * c["columns"] * 2
    return c["table_offset"], c["table_offset"] + size


@pytest.mark.parametrize("name, offset, dims, peak_ori, peak_stage", [
    ("Seat Leon", 0x1C34FC, (4, 24), 385.0, 431.8),
    ("Car 2", 0x3AAC58, (6, 21), 620.0, 620.0),
    ("Seat EDC17C64", 0x3549F2, (6, 25), 403.0, 480.0),
    ("Seat Leon EDC17C64 #2", 0x357684, (6, 25), 460.0, 500.0),
    ("VW Touareg EDC16U1", 0xDDFDE, (3, 23), 456.0, 581.5),
    ("Jaguar EDC17CP55", 0x2EB2F4, (1, 25), 700.0, 770.0),
])
def test_finds_bosch_torque_limiter(name, offset, dims, peak_ori, peak_stage):
    result = result_for(name)
    c = result["candidate"]
    assert result["map_type"] == "torque_limiter"
    assert c["layout"] in ("bosch_inline_map", "bosch_inline_curve")
    assert not c["warnings"]
    assert c["table_offset"] == offset
    assert (c["rows"], c["columns"]) == dims
    assert c["scale"] == 0.1
    assert result["summary"]["peak_ori"] == pytest.approx(peak_ori)
    assert result["summary"]["peak_stage1"] == pytest.approx(peak_stage)


@pytest.mark.parametrize("name", ["Seat EDC17C64", "Seat Leon EDC17C64 #2"])
def test_edc17c64_rpm_axis_is_half_rpm_per_count(name):
    result = result_for(name)
    graph = result["graph"]
    assert result["profile"]["key"] == "edc17c64"
    # Sea-level row; raw axis 2000..11002 is 1000..5501 rpm.
    assert graph["row_axis_value"] == 1000
    assert result["candidate"]["rpm_axis"][0] == 500
    assert result["candidate"]["rpm_axis"][-1] == 5501
    first = graph["points"][0]
    assert (first["rpm"], first["ori_torque_nm"]) == (1000, 172.0)
    assert graph["points"][-1]["rpm"] == 5500


def test_edc16_map_is_big_endian_with_rpm_one_per_count():
    result = result_for("VW Touareg EDC16U1")
    c = result["candidate"]
    assert result["profile"]["key"] == "edc16"
    assert (c["endian"], c["ecu_family"]) == ("big", "EDC16")
    assert c["row_axis"] == [700, 850, 950]
    assert c["rpm_axis"][-1] == 5300
    peak = max(result["graph"]["points"], key=lambda p: p["ori_torque_nm"])
    assert (peak["rpm"], peak["ori_torque_nm"]) == (2250, 456.0)


def test_jaguar_flags_per_gear_copies_and_removed_limits():
    options = result_for("Jaguar EDC17CP55")["map_options"]
    assert len(options) <= 6
    notes = [o["note"] for o in options]
    assert any("8 identical copies" in n for n in notes)
    removed = [
        o for o in options
        if "limit_removed_in_stage1" in o["candidate"]["warnings"]
    ]
    assert all(not o["recommended"] for o in removed)


def test_graph_drops_zero_tail_after_fuel_cut():
    points = result_for("Jaguar EDC17CP55")["graph"]["points"]
    assert points[-1]["rpm"] == 5000
    assert points[-1]["ori_torque_nm"] == points[-1]["stage_torque_nm"] == 0


@pytest.mark.parametrize("name", [p[0] for p in pairs])
def test_graphs_cover_idle_to_redline_window(name):
    for option in result_for(name)["map_options"]:
        rpms = [p["rpm"] for p in option["graph"]["points"]]
        assert rpms
        assert GRAPH_RPM_MIN <= min(rpms) and max(rpms) <= GRAPH_RPM_MAX
        assert all(b - a >= 10 for a, b in zip(rpms, rpms[1:]))


@pytest.mark.parametrize("name", [p[0] for p in pairs])
def test_alternatives_are_distinct_tables(name):
    ranges = [
        candidate_range(o["candidate"]) for o in result_for(name)["map_options"]
    ]
    for i, (s1, e1) in enumerate(ranges):
        for s2, e2 in ranges[i + 1:]:
            assert e1 <= s2 or e2 <= s1, "overlapping candidates"


def test_tiny_change_returns_review_instead_of_crashing():
    ori = (test_files / "car2_ori.bin").read_bytes()
    stage = bytearray(ori)
    # A generic (non-Bosch-header) 10 x 10 table.
    off, n = 0x3B6984, 100
    struct.pack_into(
        "<" + "H" * n, stage, off, *[x ^ 1 for x in read_u16(ori, off, n)]
    )
    result = analyse(ori, bytes(stage), "a.bin", "b.bin")
    assert result["ok"]
    assert result["confidence"] == "review"
    assert result["map_options"] == []


def test_ecu_without_torque_model_reports_changes_without_graph():
    ori = bytes(64)
    stage = bytes(32) + b"\x01" * 32
    result = analyse(ori, stage, "Seat_Ibiza_Marelli_IAW_4HV_ORI.bin", "mod.bin")
    assert result["ok"]
    assert result["map_type"] == "no_torque_model"
    assert result["map_options"] == []
    assert result["changed_regions"] == [{"offset": 32, "length": 32}]


def test_size_mismatch_is_rejected():
    with pytest.raises(ValueError):
        build_candidates(b"\0" * 64, b"\0" * 32)


@pytest.mark.parametrize("filename, key", [
    ("golf_f100.bin", "generic"),
    ("n2000_ori.bin", "generic"),
    ("bmw_f10_520d.bin", "edc17cp45_bmw"),
    ("BMW_N20B20_ori.bin", "mev1746_n20"),
    ("Delphi_DCM6.2_ori.bin", "dcm6_2"),
    ("seat_edc17c64_bench_int_flash.bin", "edc17c64"),
    ("fomoco_bosch_edc17cp55_flexray_obd_maps.bin", "edc17cp55"),
    ("edc16u1_20261005210329_Ori_ext_flash.bin", "edc16"),
    ("Seat_Ibiza_1.4i_16v_Marelli_IAW_4HV_OBD_ORI.bin", "marelli_iaw"),
])
def test_profile_matches_whole_words(filename, key):
    assert identify_profile(filename)["key"] == key


def print_report(name):
    result = result_for(name)

    print(f"\n=== {name} ===")
    print("confidence:", result["confidence"])
    print("map_type:", result["map_type"])

    if result.get("candidate"):
        c = result["candidate"]
        print(f"top candidate: 0x{c['offset']:X}")
        print(f"layout: {c['layout']}")
        print(f"dimensions: {c['rows']} x {c['columns']}")
        print(f"score: {c['score']}")
        print(f"axis confidence: {c['axis_confidence']}%")
        print(f"map confidence: {c['map_confidence']}%")

    if result.get("graph"):
        g = result["graph"]
        points = g.get("points", [])
        print("graph range:", g.get("range"))
        print("scale:", g.get("scale"))
        print("graph points:", len(points))
        if points:
            peak = max(points, key=lambda p: p["stage_torque_nm"])
            print(
                "peak stage torque:", peak["stage_torque_nm"],
                "Nm at", peak.get("rpm", peak.get("x")), "RPM",
            )
            print("maximum torque gain:", max(p["gain_nm"] for p in points), "Nm")

    print("top candidates:")
    for i, c in enumerate(result.get("candidates", [])[:5], 1):
        print(
            f"  #{i} 0x{c['offset']:X} "
            f"{c['rows']}x{c['columns']} {c['layout']} "
            f"score={c['score']}"
        )


if __name__ == "__main__":
    for name, _, _ in pairs:
        print_report(name)
