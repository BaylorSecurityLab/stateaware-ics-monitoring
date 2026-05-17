from pathlib import Path

import pandas as pd
import yaml

from dataio.ingest import ingest_topology
from dataio.loader import load_topology


def test_ingest_ctown_from_synthetic_csv(tmp_path: Path):
    raw = tmp_path / "raw" / "BATADAL"
    raw.mkdir(parents=True)
    train = pd.DataFrame({
        "DATETIME": ["01/01/17 00", "01/01/17 01", "01/01/17 02"],
        "L_T1": [1.0, 1.1, 1.2], "ATT_FLAG": [0, 0, 0],
    })
    train.to_csv(raw / "BATADAL_dataset03_train_1.csv", index=False)
    test = pd.DataFrame({
        "DATETIME": ["16/01/17 08", "16/01/17 09", "16/01/17 10"],
        "L_T1": [1.0, 5.0, 5.0],
    })
    test.to_csv(raw / "BATADAL_test_dataset.csv", index=False)

    data_root = tmp_path / "data"
    ingest_topology("ctown", raw_root=tmp_path / "raw", data_root=data_root)

    man = yaml.safe_load(
        (data_root / "ctown" / "dataset" / "dataset_manifest.yaml").read_text())
    assert "C-Town" in man["source"]["note"]

    d = load_topology("ctown", data_root=data_root)
    assert "l_t1" in d.calibration_frames[0].columns
    sc = d.eval_scenarios[0]
    # A8 window 16/01/17 09 -> 19/01/17 06 marks rows 1,2 as attack
    assert sc.labels.tolist() == [0, 1, 1]
