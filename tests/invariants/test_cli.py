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
