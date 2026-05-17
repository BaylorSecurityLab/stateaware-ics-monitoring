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
    gfsm_dir = tmp_path / "gfsm"
    (gfsm_dir / "__pycache__").mkdir(parents=True)   # stray, must be ignored
    (gfsm_dir / "bogus").mkdir()                      # dir without .gfsm.json
    # 'bogus' has no bogus.gfsm.json so it is NOT discovered → no error,
    # no topologies → overall_ok stays True → rc 0.
    rc = main(["--all", "--gfsm-dir", str(gfsm_dir),
               "--data-root", str(tmp_path), "--out", str(tmp_path / "o")])
    assert rc == 0  # nothing discovered (stray/.gfsm-less dirs excluded)


def test_all_processes_only_dirs_with_gfsm_json(tmp_path: Path, capsys):
    gfsm_dir = tmp_path / "gfsm"
    good = gfsm_dir / "synthx"
    good.mkdir(parents=True)
    (good / "synthx.gfsm.json").write_text(json.dumps({
        "initial": "PLC1:0", "states": {"PLC1:0": ["0"]},
        "transitions": [], "metadata": {"source_file": "x",
            "extraction_date": "", "total_states": 1, "total_transitions": 0},
        "max_states": 100,
    }))
    # 'synthx' discovered but get_profile('synthx') raises StlError → caught
    # as a clean config error → rc 2, message on stderr, no crash.
    rc = main(["--all", "--gfsm-dir", str(gfsm_dir),
               "--data-root", str(tmp_path), "--out", str(tmp_path / "o")])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
