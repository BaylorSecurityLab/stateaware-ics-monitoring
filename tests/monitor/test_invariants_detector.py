import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monitor.invariants_detector import InvariantsAnomalyDetector
from monitor.model import MonitorError


def _phi(tmp_path: Path, name: str = "synth", gfsm_sha: str = "0" * 64):
    inv_dir = tmp_path / "invariants"
    inv_dir.mkdir()
    (inv_dir / f"{name}_phi.json").write_text(json.dumps({
        "schema": "invariants/v1", "topology": name,
        "gfsm_manifest": f"{name}_gfsm_manifest.json",
        "gfsm_manifest_sha256": gfsm_sha,
        "dataset_manifest": "dataset_manifest.yaml",
        "dataset_manifest_sha256": "0" * 64,
        "niaarm": {}, "generated_at": "",
        "states": {
            "PLC1.S:0": {"observations": 100, "status": "ok", "rules": [
                {"id": "r0",
                 "antecedent": [{"col": "t1", "op": "in",
                                 "val": [None, None]}],
                 "consequent": [{"col": "t1", "op": "in",
                                 "val": [1.0, 1.5]}],
                 "support": 0.9, "confidence": 0.95, "lift": 1.0}
            ]},
            "PLC1.S:1": {"observations": 100, "status": "ok", "rules": []},
        },
    }))
    return inv_dir


def _gfsm_dir(tmp_path: Path, name: str = "synth", sha_text: str = "{}"):
    gd = tmp_path / "gfsm"
    gd.mkdir()
    (gd / f"{name}_gfsm_manifest.json").write_text(sha_text)
    return gd


def test_clean_within_bounds_no_flags(tmp_path: Path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv_dir = _phi(tmp_path, gfsm_sha=sha)
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    frame = pd.DataFrame({"p1": [0, 0, 0], "t1": [1.2, 1.3, 1.4]})
    out = det.predict(frame)
    assert (out.flags == 0).all()


def test_out_of_bounds_flagged(tmp_path: Path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv_dir = _phi(tmp_path, gfsm_sha=sha)
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    frame = pd.DataFrame({"p1": [0, 0], "t1": [1.2, 2.0]})  # row1 out of [1,1.5]
    out = det.predict(frame)
    assert out.flags[0] == 0 and out.flags[1] == 1


def test_unknown_state_flagged(tmp_path: Path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv_dir = _phi(tmp_path, gfsm_sha=sha)
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    out = det.predict(pd.DataFrame({"p1": [2], "t1": [1.2]}))  # PLC1.S:2 ∉ Φ
    assert out.flags[0] == 1


def test_missing_phi_raises(tmp_path: Path):
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=tmp_path / "nope", gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    )
    with pytest.raises(MonitorError, match="phi json not found"):
        det.fit([])


def test_stale_phi_raises(tmp_path: Path):
    # Φ records gfsm_manifest_sha256 = all-zeros, but the actual gfsm
    # manifest hashes to something else → stale → MonitorError.
    inv_dir = _phi(tmp_path, gfsm_sha="0" * 64)
    gd = _gfsm_dir(tmp_path, sha_text="DIFFERENT CONTENT")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    )
    with pytest.raises(MonitorError, match="stale"):
        det.fit([])


def test_stale_dataset_manifest_raises(tmp_path: Path):
    gsha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv_dir = _phi(tmp_path, gfsm_sha=gsha)
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    # Φ records dataset_manifest_sha256 = sha256("0"*64-placeholder) i.e.
    # whatever _phi wrote ("0"*64). Create a REAL dataset manifest whose
    # content hashes differently → stale.
    ds = tmp_path / "synth" / "dataset"
    ds.mkdir(parents=True)
    (ds / "dataset_manifest.yaml").write_text("files: {}\n")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    )
    with pytest.raises(MonitorError, match="dataset manifest sha mismatch"):
        det.fit([])


def test_malformed_phi_in_atom_raises(tmp_path: Path):
    gsha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv_dir = tmp_path / "invariants"
    inv_dir.mkdir()
    (inv_dir / "synth_phi.json").write_text(json.dumps({
        "schema": "invariants/v1", "topology": "synth",
        "gfsm_manifest": "synth_gfsm_manifest.json",
        "gfsm_manifest_sha256": gsha,
        "dataset_manifest": "dataset_manifest.yaml",
        "dataset_manifest_sha256": "0" * 64,
        "niaarm": {}, "generated_at": "",
        "states": {"PLC1.S:0": {"observations": 9, "status": "ok", "rules": [
            {"id": "r0",
             "antecedent": [{"col": "t1", "op": "in", "val": 1.5}],
             "consequent": [{"col": "t1", "op": "in", "val": [1.0, 1.5]}],
             "support": 0.9, "confidence": 0.95, "lift": 1.0}]}},
    }))
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    )
    with pytest.raises(MonitorError, match="malformed"):
        det.fit([])


def test_legacy_phi_without_threshold_defaults_k1(tmp_path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv = _phi(tmp_path, gfsm_sha=sha)
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    assert det._k == 1
    out = det.predict(pd.DataFrame({"p1": [0], "t1": [9.0]}))
    assert out.flags[0] == 1


def test_threshold_k_requires_enough_violations(tmp_path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv = _phi(tmp_path, gfsm_sha=sha)
    p = inv / "synth_phi.json"
    d = json.loads(p.read_text())
    d["violation_threshold"] = 2
    p.write_text(json.dumps(d))
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    assert det._k == 2
    out = det.predict(pd.DataFrame({"p1": [0], "t1": [9.0]}))
    assert out.flags[0] == 0


def test_state_absent_flags_regardless_of_k(tmp_path):
    sha = hashlib.sha256("{}".encode("utf-8")).hexdigest()
    inv = _phi(tmp_path, gfsm_sha=sha)
    p = inv / "synth_phi.json"
    d = json.loads(p.read_text())
    d["violation_threshold"] = 99
    p.write_text(json.dumps(d))
    gd = _gfsm_dir(tmp_path, sha_text="{}")
    det = InvariantsAnomalyDetector(
        invariants_dir=inv, gfsm_dir=gd, data_root=tmp_path,
        topology="synth", components=[("PLC1", "S")],
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    out = det.predict(pd.DataFrame({"p1": [7], "t1": [1.2]}))
    assert out.flags[0] == 1
