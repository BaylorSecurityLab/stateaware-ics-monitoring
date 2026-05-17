import json
from pathlib import Path

import pytest

from st_analyze.cli import main


def test_missing_manifest_returns_2(tmp_path: Path, capsys):
    rc = main(["--topology", "nope", "--generated-dir", str(tmp_path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_runs_anytown(tmp_path: Path):
    gen = Path(__file__).resolve().parents[2] / "data" / "generated"
    if not (gen / "anytown" / "anytown_manifest.json").exists():
        pytest.skip("generated anytown data missing")
    rc = main([
        "--topology", "anytown",
        "--generated-dir", str(gen),
        "--out", str(tmp_path / "analysis"),
    ])
    assert rc == 0
    assert (tmp_path / "analysis" / "anytown_analysis_manifest.json").exists()


def test_all_continues_past_bad_topology(tmp_path: Path):
    gen = tmp_path / "generated"
    # 'bad' sorts before 'good'; bad has invalid JSON, good is valid.
    (gen / "bad").mkdir(parents=True)
    (gen / "bad" / "bad_manifest.json").write_text("{ not valid json")
    (gen / "good").mkdir(parents=True)
    (gen / "good" / "good_manifest.json").write_text(json.dumps({
        "topology": "good",
        "plcs": [{"name": "PLC1", "file": "good_plc1.st", "fsms": []}],
    }))
    (gen / "good" / "good_plc1.st").write_text(
        "PROGRAM PLC1\n(* empty *)\nEND_PROGRAM\n"
    )
    rc = main(["--all", "--generated-dir", str(gen)])
    # bad topology errored, but good was still processed; rc=2 because
    # at least one topology hard-errored.
    assert rc == 2
    assert (gen / "good" / "analysis" / "good_analysis_manifest.json").exists()


def test_single_invalid_manifest_returns_2_immediately(tmp_path: Path, capsys):
    gen = tmp_path / "generated"
    (gen / "x").mkdir(parents=True)
    (gen / "x" / "x_manifest.json").write_text("{ not valid json")
    rc = main(["--topology", "x", "--generated-dir", str(gen)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_exit_code_1_when_all_ok_false(tmp_path: Path):
    gen = tmp_path / "generated"
    (gen / "syn").mkdir(parents=True)
    # PLC1's .st is absent → status "missing" → all_ok False, but no
    # StAnalyzeError → rc must be 1 (not 2, not 0).
    (gen / "syn" / "syn_manifest.json").write_text(json.dumps({
        "topology": "syn",
        "plcs": [{"name": "PLC1", "file": "syn_plc1.st", "fsms": []}],
    }))
    rc = main([
        "--topology", "syn", "--generated-dir", str(gen),
        "--out", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert (tmp_path / "out" / "syn_analysis_manifest.json").exists()
