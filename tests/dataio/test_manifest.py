from pathlib import Path

import yaml

from dataio.manifest import build_dataset_manifest, load_dataset_manifest, sha256_file


def test_sha256_file(tmp_path: Path):
    p = tmp_path / "a.csv"
    p.write_text("x\n1\n")
    assert sha256_file(p) == sha256_file(p)
    assert len(sha256_file(p)) == 64


def test_build_and_load_roundtrip(tmp_path: Path):
    f = tmp_path / "calibration" / "train.csv"
    f.parent.mkdir(parents=True)
    f.write_text("l_t1\n1.0\n")
    m = build_dataset_manifest(
        topology="ctown",
        source_name="BATADAL_dataset03_train_1.csv",
        source_note="BATADAL is the C-Town network; renamed to ctown",
        fmt="csv",
        root=tmp_path,
        calibration_files=["calibration/train.csv"],
        evaluation_files=[],
        column_map={"L_T1": "l_t1"},
        attack_windows=[("A8", "16/01/17 09", "19/01/17 06")],
    )
    out = tmp_path / "dataset_manifest.yaml"
    out.write_text(yaml.safe_dump(m, sort_keys=True))
    loaded = load_dataset_manifest(out)
    assert loaded["topology"] == "ctown"
    assert "C-Town" in loaded["source"]["note"]
    assert loaded["sha256"]["calibration/train.csv"]
    assert loaded["attack_windows"][0]["id"] == "A8"
