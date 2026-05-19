from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from dataio.loader import load_topology
from dataio.manifest import build_dataset_manifest


def _make_dataset(root: Path):
    ds = root / "ctown" / "dataset"
    (ds / "calibration").mkdir(parents=True)
    (ds / "evaluation").mkdir(parents=True)
    pd.DataFrame({"l_t1": [1.0, 2.0, 3.0]}).to_csv(
        ds / "calibration" / "train.csv", index=False)
    pd.DataFrame({"l_t1": [1.0, 9.0], "label": [0, 1]}).to_csv(
        ds / "evaluation" / "test.csv", index=False)
    m = build_dataset_manifest(
        topology="ctown", source_name="BATADAL_dataset03_train_1.csv",
        source_note="BATADAL is the C-Town network; renamed to ctown",
        fmt="csv", root=ds,
        calibration_files=["calibration/train.csv"],
        evaluation_files=["evaluation/test.csv"],
        column_map={"L_T1": "l_t1"}, attack_windows=[],
    )
    (ds / "dataset_manifest.yaml").write_text(yaml.safe_dump(m, sort_keys=True))


def test_load_topology(tmp_path: Path):
    _make_dataset(tmp_path)
    d = load_topology("ctown", data_root=tmp_path)
    assert d.topology == "ctown"
    assert len(d.calibration_frames) == 1
    assert list(d.calibration_frames[0]["l_t1"]) == [1.0, 2.0, 3.0]
    assert len(d.eval_scenarios) == 1
    sc = d.eval_scenarios[0]
    assert sc.name == "test"
    assert "label" not in sc.frame.columns
    assert sc.labels.tolist() == [0, 1]


def test_missing_dataset_raises(tmp_path: Path):
    import pytest
    from dataio.model import DataIoError
    with pytest.raises(DataIoError):
        load_topology("nope", data_root=tmp_path)
