from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("rtamt")

from stl.driver import run_topology

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
DS = DATA / "ltown" / "dataset" / "dataset_manifest.yaml"


@pytest.mark.skipif(not DS.exists(), reason="normalized ltown dataset missing")
def test_ltown_formulas_and_held_out_normal(tmp_path: Path):
    out = tmp_path / "stl"
    m = run_topology(topology="ltown", data_root=DATA, out_dir=out, jobs=1)
    assert m["n_formulas"] > 0, "vacuous: no STL formulas synthesized"
    assert m["scenarios"], "vacuous: no eval scenarios"
    pred = pd.read_csv(out / "predictions.csv")
    assert len(pred) > 0
    assert {"scenario", "y_true", "y_pred"}.issubset(pred.columns)
    # ltown evaluation is a held-out NORMAL split: no labeled attacks.
    assert pred["y_true"].sum() == 0


@pytest.mark.skipif(not DS.exists(), reason="normalized ltown dataset missing")
def test_ltown_determinism_jobs1_vs_jobs4(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    run_topology(topology="ltown", data_root=DATA, out_dir=a, jobs=1)
    run_topology(topology="ltown", data_root=DATA, out_dir=b, jobs=4)
    for name in ["stl_formulas.txt", "predictions.csv"]:
        assert (a / name).read_text() == (b / name).read_text(), name
