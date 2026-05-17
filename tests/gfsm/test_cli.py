import json
from pathlib import Path

from gfsm.cli import main
from tests.gfsm.test_driver import _stage2


def test_missing_manifest_returns_2(tmp_path: Path, capsys):
    rc = main(["--topology", "nope", "--generated-dir", str(tmp_path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_runs_single_topology(tmp_path: Path):
    gen = tmp_path / "generated"
    _stage2(gen, "syn")
    rc = main([
        "--topology", "syn", "--generated-dir", str(gen),
        "--out-dir", str(tmp_path / "g"),
    ])
    assert rc == 0
    assert (tmp_path / "g" / "syn_gfsm_manifest.json").exists()


def test_all_continues_past_bad_topology(tmp_path: Path):
    gen = tmp_path / "generated"
    (gen / "bad" / "analysis").mkdir(parents=True)
    (gen / "bad" / "analysis" / "bad_analysis_manifest.json").write_text(
        "{ not valid json"
    )
    _stage2(gen, "good")
    rc = main(["--all", "--generated-dir", str(gen)])
    assert rc == 2  # bad hard-errored; good still processed
    assert (gen / "good" / "gfsm" / "good_gfsm_manifest.json").exists()


def test_single_invalid_manifest_returns_2(tmp_path: Path, capsys):
    gen = tmp_path / "generated"
    (gen / "x" / "analysis").mkdir(parents=True)
    (gen / "x" / "analysis" / "x_analysis_manifest.json").write_text(
        "{ not valid json"
    )
    rc = main(["--topology", "x", "--generated-dir", str(gen)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_exit_code_1_when_all_ok_false(tmp_path: Path):
    gen = tmp_path / "generated"
    ad = (gen / "syn" / "analysis")
    ad.mkdir(parents=True)
    # PLC's ast.xml referenced but absent -> extraction error -> all_ok False
    ad.joinpath("syn_analysis_manifest.json").write_text(json.dumps({
        "schema": "st_analyze/v1", "topology": "syn",
        "plcs": [{"name": "PLC1", "st_file": "syn_plc1.st", "status": "ok",
                  "artifacts": {"ast_xml": "syn_plc1.ast.xml"},
                  "st_gen_fsms": ["FB"]}],
    }))
    rc = main([
        "--topology", "syn", "--generated-dir", str(gen),
        "--out-dir", str(tmp_path / "o"),
    ])
    assert rc == 1
    assert (tmp_path / "o" / "syn_gfsm_manifest.json").exists()


def test_max_states_overflow_returns_2(tmp_path: Path, capsys):
    gen = tmp_path / "generated"
    _stage2(gen, "syn")
    rc = main([
        "--topology", "syn", "--generated-dir", str(gen),
        "--out-dir", str(tmp_path / "o"), "--max-states", "1",
    ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
