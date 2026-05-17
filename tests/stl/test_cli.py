from pathlib import Path

import pandas as pd
import pytest
import yaml

pytest.importorskip("rtamt")

from dataio.manifest import build_dataset_manifest
from stl.cli import main


def _seed_ctown(data_root: Path):
    ds = data_root / "ctown" / "dataset"
    (ds / "calibration").mkdir(parents=True)
    (ds / "evaluation").mkdir(parents=True)
    import numpy as np
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


def test_cli_topology_writes_artifacts(tmp_path: Path):
    _seed_ctown(tmp_path)
    rc = main(["--topology", "ctown", "--data-root", str(tmp_path),
               "--jobs", "1"])
    assert rc == 0
    out = tmp_path / "generated" / "ctown" / "stl"
    assert (out / "stl_formulas.txt").exists()
    assert (out / "predictions.csv").exists()
    assert (out / "evaluation.json").exists()
    assert (out / "ctown_stl_manifest.json").exists()


def test_cli_unknown_topology_returns_2(tmp_path: Path):
    assert main(["--topology", "ltown", "--data-root", str(tmp_path)]) == 2
