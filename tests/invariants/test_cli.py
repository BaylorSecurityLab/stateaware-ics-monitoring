import json
from pathlib import Path

import pandas as pd

from invariants.cli import main


def test_missing_gfsm_returns_2(tmp_path: Path, capsys):
    rc = main(["--topology", "nope", "--gfsm-dir", str(tmp_path),
               "--data-root", str(tmp_path), "--out", str(tmp_path / "out")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_runs_anytown_if_present(tmp_path: Path):
    repo = Path(__file__).resolve().parents[2]
    gfsm_dir = repo / "data" / "generated" / "anytown" / "gfsm"
    ds = repo / "data" / "anytown" / "dataset" / "dataset_manifest.yaml"
    if not (gfsm_dir / "anytown.gfsm.json").exists() or not ds.exists():
        import pytest
        pytest.skip("anytown gfsm or dataset missing")
    rc = main(["--topology", "anytown",
               "--gfsm-dir", str(gfsm_dir),
               "--data-root", str(repo / "data"),
               "--out", str(tmp_path / "inv"),
               "--max-evals", "300"])
    assert rc in (0, 1)
    assert (tmp_path / "inv" / "anytown_phi.json").exists()


def test_all_skips_stray_dirs_and_continues(tmp_path: Path, capsys):
    gen_root = tmp_path / "generated"
    (gen_root / "__pycache__").mkdir(parents=True)   # stray, must be ignored
    (gen_root / "bogus" / "gfsm").mkdir(parents=True)  # dir without .gfsm.json
    # 'bogus' has no bogus/gfsm/bogus.gfsm.json so it is NOT discovered →
    # zero topologies found → hard error rc 2.
    rc = main(["--all", "--data-root", str(tmp_path)])
    assert rc == 2  # empty discovery is a hard error, not silent rc 0
    assert "error:" in capsys.readouterr().err


def test_all_processes_only_dirs_with_gfsm_json(tmp_path: Path, capsys):
    # canonical layout: <data_root>/generated/<topo>/gfsm/<topo>.gfsm.json
    good = tmp_path / "generated" / "synthx" / "gfsm"
    good.mkdir(parents=True)
    (good / "synthx.gfsm.json").write_text(json.dumps({
        "initial": "PLC1:0", "states": {"PLC1:0": ["0"]},
        "transitions": [], "metadata": {"source_file": "x",
            "extraction_date": "", "total_states": 1, "total_transitions": 0},
        "max_states": 100,
    }))
    # 'synthx' discovered but get_profile('synthx') raises StlError → caught
    # as a clean config error → rc 2, message on stderr, no crash.
    rc = main(["--all", "--data-root", str(tmp_path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_fp_budget_arg_default_and_validation():
    from invariants.cli import _build_parser
    p = _build_parser()
    ns = p.parse_args(["--all"])
    assert ns.fp_budget == 0.01
    ns2 = p.parse_args(["--all", "--fp-budget", "0.05"])
    assert ns2.fp_budget == 0.05


def test_fp_budget_invalid_returns_error(capsys):
    from invariants.cli import main
    rc = main(["--topology", "x", "--data-root", "/nonexistent",
               "--fp-budget", "0"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "fp-budget" in err or "fp_budget" in err
