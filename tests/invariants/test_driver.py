import json
from pathlib import Path

import pandas as pd
import pytest

from invariants.driver import mine_topology
from invariants.model import InvariantsError


def test_missing_gfsm_raises(tmp_path: Path):
    with pytest.raises(InvariantsError, match="gfsm json not found"):
        mine_topology(topology="nope", data_root=tmp_path, gfsm_dir=tmp_path,
                      out_dir=tmp_path / "out", fb_to_col={})


def test_mine_topology_writes_phi_and_manifest(tmp_path: Path):
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "synth.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0",
        "states": {"PLC1.S:0": ["0"], "PLC1.S:1": ["1"]},
        "transitions": [], "metadata": {"source_file": "x",
            "extraction_date": "", "total_states": 2, "total_transitions": 0},
        "max_states": 100,
    }))
    (gfsm_dir / "synth_gfsm_manifest.json").write_text(json.dumps({"x": 1}))

    ds_dir = tmp_path / "synth" / "dataset"
    ds_dir.mkdir(parents=True)
    (ds_dir / "dataset_manifest.yaml").write_text(
        "files:\n  calibration:\n    - cal.csv\n  evaluation: []\n"
        "column_map: {}\nattack_windows: []\n"
    )
    cal = pd.DataFrame({
        "p1": [0]*60 + [1]*60,
        "t1": [1.0]*60 + [2.0]*60,
        "f1": [0.5]*60 + [0.7]*60,
    })
    cal.to_csv(ds_dir / "cal.csv", index=False)

    fb_to_col = {("PLC1", "S"): "p1"}
    out = tmp_path / "synth" / "invariants"
    m = mine_topology(
        topology="synth", data_root=tmp_path, gfsm_dir=gfsm_dir,
        out_dir=out, fb_to_col=fb_to_col, min_observations=50, max_evals=200,
        seed=42, feature_cols=["t1", "f1"],
    )
    assert (out / "synth_phi.json").exists()
    assert (out / "synth_invariants_manifest.json").exists()
    phi = json.loads((out / "synth_phi.json").read_text())
    assert phi["schema"] == "invariants/v1"
    assert "PLC1.S:0" in phi["states"] or "PLC1.S:1" in phi["states"]
    assert m["all_ok"] in (True, False)
    # Φ JSON must be serializable end-to-end (it was just written, re-load it):
    json.loads((out / "synth_phi.json").read_text())


def test_missing_gfsm_manifest_raises(tmp_path: Path):
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "synth.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0", "states": {"PLC1.S:0": ["0"]},
        "transitions": [], "metadata": {"source_file": "x",
            "extraction_date": "", "total_states": 1, "total_transitions": 0},
        "max_states": 100,
    }))
    # gfsm json present but the _gfsm_manifest.json is absent
    with pytest.raises(InvariantsError, match="gfsm manifest not found"):
        mine_topology(topology="synth", data_root=tmp_path,
                      gfsm_dir=gfsm_dir, out_dir=tmp_path / "out",
                      fb_to_col={("PLC1", "S"): "p1"})


def test_missing_dataset_manifest_raises(tmp_path: Path):
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "synth.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0", "states": {"PLC1.S:0": ["0"]},
        "transitions": [], "metadata": {"source_file": "x",
            "extraction_date": "", "total_states": 1, "total_transitions": 0},
        "max_states": 100,
    }))
    (gfsm_dir / "synth_gfsm_manifest.json").write_text(json.dumps({"x": 1}))
    # no data_root/synth/dataset/dataset_manifest.yaml
    with pytest.raises(InvariantsError, match="dataset manifest not found"):
        mine_topology(topology="synth", data_root=tmp_path,
                      gfsm_dir=gfsm_dir, out_dir=tmp_path / "out",
                      fb_to_col={("PLC1", "S"): "p1"})
