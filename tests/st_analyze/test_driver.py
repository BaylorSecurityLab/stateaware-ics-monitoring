import json
from pathlib import Path

import pytest

from st_analyze.driver import analyze_topology
from st_analyze.model import StAnalyzeError


def test_missing_topology_raises(tmp_path: Path):
    with pytest.raises(StAnalyzeError, match="manifest not found"):
        analyze_topology(generated_dir=tmp_path, topology="nope", out_dir=None)


def test_analyze_topology_writes_artifacts(repo_data, tmp_path: Path):
    gen = repo_data / "generated"
    if not (gen / "anytown" / "anytown_manifest.json").exists():
        pytest.skip("generated anytown data missing")

    out = tmp_path / "analysis"
    manifest = analyze_topology(
        generated_dir=gen, topology="anytown", out_dir=out
    )

    assert (out / "anytown_analysis_manifest.json").exists()
    assert (out / "anytown_plc1.ast.xml").exists()
    assert (out / "anytown_plc1.invariants.json").exists()
    assert (out / "anytown_plc1.pdg.dot").exists()
    assert (out / "anytown_plc1.pdg.json").exists()

    plc1 = next(p for p in manifest["plcs"] if p["name"] == "PLC1")
    assert plc1["status"] == "ok"
    invs = json.loads((out / "anytown_plc1.invariants.json").read_text())
    assert isinstance(invs, list)
    assert plc1["counts"]["pdg_nodes"] >= 1


def test_missing_st_file_entry_has_errors_key_and_stops(tmp_path: Path):
    topo = tmp_path / "synth"
    topo.mkdir()
    (topo / "synth_manifest.json").write_text(json.dumps({
        "topology": "synth",
        "plcs": [
            {"name": "PLC1", "file": "synth_plc1.st",
             "fsms": [{"actuator": "P1", "states": 2, "transitions": 2}]},
            {"name": "PLC2", "file": "synth_plc2.st", "fsms": []},
        ],
    }))
    # PLC1's .st intentionally absent → "missing"; PLC2 never reached
    m = analyze_topology(
        generated_dir=tmp_path, topology="synth", out_dir=tmp_path / "out"
    )
    assert m["all_ok"] is False
    assert len(m["plcs"]) == 1  # keep_going=False stops after PLC1
    miss = m["plcs"][0]
    assert miss["status"] == "missing"
    assert miss["errors"] == ["st file not found: synth_plc1.st"]


def test_keep_going_processes_all_plcs(tmp_path: Path):
    topo = tmp_path / "synth"
    topo.mkdir()
    (topo / "synth_manifest.json").write_text(json.dumps({
        "topology": "synth",
        "plcs": [
            {"name": "PLC1", "file": "synth_plc1.st", "fsms": []},
            {"name": "PLC2", "file": "synth_plc2.st", "fsms": []},
        ],
    }))
    m = analyze_topology(
        generated_dir=tmp_path, topology="synth",
        out_dir=tmp_path / "out", keep_going=True,
    )
    assert len(m["plcs"]) == 2  # both processed despite both missing
    assert all(p["status"] == "missing" for p in m["plcs"])
    assert m["all_ok"] is False


def test_fsm_listed_but_empty_pdg_is_error(tmp_path: Path):
    topo = tmp_path / "synth"
    topo.mkdir()
    # Empty PROGRAM → analyzer parses OK but produces no PDG nodes,
    # while the manifest claims this PLC has an FSM.
    (topo / "synth_plc1.st").write_text(
        "PROGRAM PLC1\n(* no actuators *)\nEND_PROGRAM\n"
    )
    (topo / "synth_manifest.json").write_text(json.dumps({
        "topology": "synth",
        "plcs": [
            {"name": "PLC1", "file": "synth_plc1.st",
             "fsms": [{"actuator": "P1", "states": 2, "transitions": 2}]},
        ],
    }))
    m = analyze_topology(
        generated_dir=tmp_path, topology="synth", out_dir=tmp_path / "out"
    )
    plc1 = m["plcs"][0]
    assert plc1["status"] == "error"
    assert "st_gen manifest lists FSMs but PDG is empty" in plc1["errors"]
    assert m["all_ok"] is False


def test_parse_failure_with_fsms_has_no_spurious_crosscheck_error(tmp_path: Path):
    topo = tmp_path / "synth"
    topo.mkdir()
    # Unparseable ST → analyze_source returns ok=False with a parse error
    # and an empty PDG. The manifest also lists an FSM for this PLC.
    (topo / "synth_plc1.st").write_text(
        "@@@ this is definitely not structured text @@@\n"
    )
    (topo / "synth_manifest.json").write_text(json.dumps({
        "topology": "synth",
        "plcs": [
            {"name": "PLC1", "file": "synth_plc1.st",
             "fsms": [{"actuator": "P1", "states": 2, "transitions": 2}]},
        ],
    }))
    m = analyze_topology(
        generated_dir=tmp_path, topology="synth", out_dir=tmp_path / "out"
    )
    plc1 = m["plcs"][0]
    assert plc1["status"] == "error"
    # The real cause (parse failure) must be reported...
    assert any("parse failed" in e for e in plc1["errors"])
    # ...and the spurious FSM/PDG cross-check message must NOT appear.
    assert "st_gen manifest lists FSMs but PDG is empty" not in plc1["errors"]
    assert m["all_ok"] is False
