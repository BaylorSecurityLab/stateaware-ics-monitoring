from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

pytest.importorskip("rtamt")

from dataio.manifest import build_dataset_manifest
from monitor.cli import main


def _seed(data_root: Path):
    ds = data_root / "ctown" / "dataset"
    (ds / "calibration").mkdir(parents=True)
    (ds / "evaluation").mkdir(parents=True)
    rng = np.random.default_rng(0)
    pd.DataFrame({"l_t1": rng.uniform(2.0, 3.0, 1200)}).to_csv(
        ds / "calibration" / "calibration.csv", index=False)
    pd.DataFrame({"l_t1": [2.5] * 6 + [999.0] * 6,
                  "label": [0] * 6 + [1] * 6}).to_csv(
        ds / "evaluation" / "test.csv", index=False)
    m = build_dataset_manifest(
        topology="ctown", source_name="synthetic", source_note="C-Town synthetic",
        fmt="csv", root=ds, calibration_files=["calibration/calibration.csv"],
        evaluation_files=["evaluation/test.csv"], column_map={}, attack_windows=[])
    (ds / "dataset_manifest.yaml").write_text(yaml.safe_dump(m, sort_keys=True))


def test_ics_monitor_or_equals_stl_when_gfsm_stubbed(tmp_path: Path):
    _seed(tmp_path)
    rc = main(["--topology", "ctown", "--data-root", str(tmp_path),
               "--jobs", "1"])
    assert rc == 0
    pred = pd.read_csv(
        tmp_path / "generated" / "ctown" / "monitor" / "predictions.csv")
    assert (pred["y_pred"] == pred["y_pred_stl"]).all()
    assert pred["y_pred_gfsm"].sum() == 0
