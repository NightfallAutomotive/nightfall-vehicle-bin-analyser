"""Tests for change descriptions and single-file analysis."""
import shutil
from functools import cache
from pathlib import Path

import pytest

from changes import (
    OriLibrary,
    analyse_single,
    describe_changes,
    pattern_checks,
    software_ids,
)

test_files = Path(__file__).parent / "test-files"


@cache
def read(name):
    return (test_files / name).read_bytes()


@cache
def x5_changes():
    # BMW X5 EDC17C56: EGR, SCR, exhaust flap and Vmax off, no tune
    return describe_changes(read("edc17c56_ori.bin"), read("edc17c56_mod.bin"))


def test_software_id_is_kept_by_the_modified_file():
    assert software_ids(read("edc17c56_ori.bin"))[0] == "1037550602"
    assert software_ids(read("edc17c56_mod.bin"))[0] == "1037550602"


def test_bmw_fault_checks_and_codes():
    faults = x5_changes()["faults"]
    assert faults["verified"]
    assert faults["fault_checks_off"] == 250
    assert faults["fault_checks_total"] == 1489
    codes = {c["code"]: c["checks"] for c in faults["codes"]}
    assert len(codes) == 46
    assert codes["CD94"] == 131
    assert codes["CD95"] == 75
    assert sum(codes.values()) == 250


def test_bmw_speed_limiter_raised():
    (limit,) = x5_changes()["speed_limits"]
    assert limit["count"] == 16
    assert limit["new_kmh"] == 350
    assert (min(limit["old_kmh"]), max(limit["old_kmh"])) == (198, 257)


def test_vag_speed_limiter_raised_in_stage1():
    changes = describe_changes(read("edc17c64_ori.bin"), read("edc17c64_stage1.bin"))
    assert {s["new_kmh"] for s in changes["speed_limits"]} == {295}
    assert sum(s["count"] for s in changes["speed_limits"]) == 8
    # A tune with no emissions work switches no fault checks off
    assert not changes["faults"]["verified"]
    assert changes["faults"]["fault_checks_off"] < 10


@pytest.mark.parametrize("ori, mod", [
    ("edc16u1_ori.bin", "edc16u1_stage1.bin"),
    ("ori.bin", "stage1.bin"),
    ("car2_ori.bin", "car2_stage1.bin"),
])
def test_torque_only_tunes_report_no_false_changes(ori, mod):
    changes = describe_changes(read(ori), read(mod))
    assert changes["speed_limits"] == []
    assert not any("fault" in line.lower() for line in changes["summary"])


def test_single_file_uses_library_original(tmp_path):
    shutil.copy(test_files / "edc17c56_ori.bin", tmp_path / "anything.bin")
    result = analyse_single(read("edc17c56_mod.bin"), "test.bin", OriLibrary(tmp_path))
    assert result["comparison"] == {
        "mode": "library", "software": "1037550602", "reference": "anything.bin",
    }
    assert result["changes"]["faults"]["fault_checks_off"] == 250


def test_single_file_with_torque_tune_graphs_against_library(tmp_path):
    shutil.copy(test_files / "edc17c64_ori.bin", tmp_path / "c64.bin")
    result = analyse_single(read("edc17c64_stage1.bin"), "", OriLibrary(tmp_path))
    assert result["map_type"] == "torque_limiter"
    assert result["summary"]["peak_stage1"] == pytest.approx(480.0)


def test_single_file_identical_to_library_original(tmp_path):
    shutil.copy(test_files / "edc17c56_ori.bin", tmp_path / "x5.bin")
    result = analyse_single(read("edc17c56_ori.bin"), "", OriLibrary(tmp_path))
    assert result["map_type"] == "unchanged"


def test_single_file_without_library_match_falls_back_to_patterns(tmp_path):
    result = analyse_single(read("edc17cp55_stage1.bin"), "", OriLibrary(tmp_path))
    assert result["comparison"]["mode"] == "pattern"
    assert any("switched off (set to 1000 Nm)" in f for f in result["patterns"]["findings"])


@pytest.mark.parametrize("name, peak", [
    ("edc17c64_ori.bin", 403.0),
    ("edc16u1_ori.bin", 456.0),
    ("ori.bin", 385.0),
])
def test_pattern_checks_find_the_torque_limiter_map(name, peak):
    limiters = pattern_checks(read(name))["limiters"]
    assert limiters[0]["peak_nm"] == peak


# ---------- Saving uploaded originals ----------

def test_uploaded_original_is_saved_without_its_filename(tmp_path):
    library = OriLibrary(tmp_path)
    outcome = library.add(read("edc17c56_ori.bin"))
    assert outcome == {"saved": True, "software": "1037550602"}
    (saved,) = (tmp_path / "uploads").iterdir()
    assert saved.name.startswith("1037550602_") and saved.suffix == ".bin"
    assert saved.read_bytes() == read("edc17c56_ori.bin")
    # Usable straight away for single-file checks
    assert library.find(read("edc17c56_mod.bin"))[0] == saved


def test_uploaded_original_is_not_saved_twice(tmp_path):
    library = OriLibrary(tmp_path)
    library.add(read("edc17c56_ori.bin"))
    assert library.add(read("edc17c56_ori.bin"))["reason"] == "already in the library"
    assert len(list((tmp_path / "uploads").iterdir())) == 1


def test_file_without_software_number_is_not_saved(tmp_path):
    outcome = OriLibrary(tmp_path).add(bytes(512 * 1024))
    assert not outcome["saved"]
    assert not (tmp_path / "uploads").exists()


def test_curated_original_wins_over_uploaded_one(tmp_path):
    # Someone uploads an already-tuned file as their "original"
    shutil.copy(test_files / "edc17c64_ori.bin", tmp_path / "stock.bin")
    library = OriLibrary(tmp_path)
    library.add(read("edc17c64_stage1.bin"))
    path, _, _ = library.find(read("edc17c64_stage1.bin"))
    assert path.name == "stock.bin"


def test_web_upload_saves_original_unless_opted_out(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app

    monkeypatch.setattr(app, "LIBRARY", OriLibrary(tmp_path))
    client = TestClient(app.app)
    files = lambda: {
        "ori": ("SR16YED_x5_ori.bin", read("edc17c56_ori.bin")),
        "stage1": ("test.bin", read("edc17c56_mod.bin")),
    }

    kept_private = client.post("/analyse", files=files(), data={"save_original": "false"}).json()
    assert kept_private["library"]["saved"] is False
    assert not (tmp_path / "uploads").exists()

    saved = client.post("/analyse", files=files()).json()
    assert saved["library"] == {"saved": True, "software": "1037550602"}
    assert not any("SR16YED" in p.name for p in (tmp_path / "uploads").iterdir())

    single = client.post("/analyse", files={"ori": ("test.bin", read("edc17c56_mod.bin"))}).json()
    assert single["comparison"]["mode"] == "library"
    assert single["changes"]["faults"]["fault_checks_off"] == 250
