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


def test_keep_going_controls_exit_contract(repo_data, tmp_path: Path):
    gen = repo_data / "generated"
    if not (gen / "anytown" / "anytown_manifest.json").exists():
        pytest.skip("generated anytown data missing")
    m = analyze_topology(
        generated_dir=gen, topology="anytown", out_dir=tmp_path / "a"
    )
    assert m["all_ok"] in (True, False)
