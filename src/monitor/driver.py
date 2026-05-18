"""Hybrid driver: STL physics + GFSM δ + Φ invariants per scenario, fuse.

Detectors load pre-built artifacts (gfsm json, Φ json) at fit() — nothing
is re-mined/re-extracted at predict time. Default fusion is the paper's
intersection rule: (gfsm OR invariants) AND stl; --fusion or = baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from dataio.loader import load_topology
from dataio.model import DataIoError
from invariants.model import InvariantsError
from invariants.state_label import load_gfsm_components, resolve_fb_to_col
from stl.metrics import detection_metrics
from stl.profiles import get_profile

from .fusion import fuse_intersection, fuse_or
from .gfsm_detector import GfsmAnomalyDetector
from .invariants_detector import InvariantsAnomalyDetector
from .model import MonitorError
from .stl_detector import StlAnomalyDetector


def run_topology(*, topology: str, data_root: Path, out_dir: Path | None,
                  fusion: str = "intersection",
                  jobs: int | None = None) -> dict[str, Any]:
    profile = get_profile(topology)
    try:
        dataset = load_topology(topology, data_root=data_root)
    except DataIoError as exc:
        raise MonitorError(str(exc)) from exc

    out = (Path(out_dir) if out_dir is not None
           else Path(data_root) / "generated" / topology / "monitor")
    out.mkdir(parents=True, exist_ok=True)

    gfsm_dir = Path(data_root) / "generated" / topology / "gfsm"
    inv_dir = Path(data_root) / "generated" / topology / "invariants"
    gfsm_path = gfsm_dir / f"{topology}.gfsm.json"
    if not gfsm_path.exists():
        raise MonitorError(
            f"gfsm json not found: {gfsm_path} (run gfsm-build)")
    gman_path = gfsm_dir / f"{topology}_gfsm_manifest.json"
    if not gman_path.exists():
        raise MonitorError(f"gfsm manifest not found: {gman_path}")
    ds_man = Path(data_root) / topology / "dataset" / "dataset_manifest.yaml"
    if not ds_man.exists():
        raise MonitorError(f"dataset manifest not found: {ds_man}")
    import yaml
    components = load_gfsm_components(json.loads(gfsm_path.read_text()))
    gfsm_manifest = json.loads(gman_path.read_text())
    col_map = (yaml.safe_load(ds_man.read_text()) or {}).get("column_map") or {}
    try:
        fb_to_col = resolve_fb_to_col(components, gfsm_manifest, col_map)
    except InvariantsError as exc:
        raise MonitorError(str(exc)) from exc

    stl_det = StlAnomalyDetector(profile, jobs=jobs).fit(
        dataset.calibration_frames)
    gfsm_det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology=topology, fb_to_col=fb_to_col).fit([])
    inv_det = InvariantsAnomalyDetector(
        invariants_dir=inv_dir, gfsm_dir=gfsm_dir, data_root=Path(data_root),
        topology=topology, components=components, fb_to_col=fb_to_col).fit([])

    rows, scen = [], []
    for sc in dataset.eval_scenarios:
        s = stl_det.predict(sc.frame)
        g = gfsm_det.predict(sc.frame)
        v = inv_det.predict(sc.frame)
        if fusion == "intersection":
            fused = fuse_intersection([g.flags, v.flags], [s.flags])
        else:
            fused = fuse_or([s.flags, g.flags, v.flags])
        y = sc.labels.astype(int)
        scen.append({
            "name": sc.name, "n": int(len(y)),
            "attack_rows": int(y.sum()),
            # STL is the only detector with a continuous score; use it as
            # the threshold-free ranking signal even when the fused
            # decision came from gfsm/invariants.
            "metrics": detection_metrics(
                y, fused,
                s.scores if s.scores is not None else fused.astype(float)),
        })
        for i in range(len(y)):
            rows.append({"scenario": sc.name, "row": i,
                         "y_true": int(y[i]),
                         "y_pred_stl": int(s.flags[i]),
                         "y_pred_gfsm": int(g.flags[i]),
                         "y_pred_invariants": int(v.flags[i]),
                         "y_pred": int(fused[i])})

    pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False)
    # all_ok is structurally always True here: the three detectors load
    # their artifacts and raise MonitorError at fit() BEFORE this loop, and
    # a predict()-time exception is a real bug that must propagate (not be
    # swallowed into all_ok=False). Unlike stl/gfsm drivers there is no
    # partial-per-scenario-failure path, so this is intentionally a literal.
    manifest = {
        "schema": "monitor/v1", "topology": topology,
        "detectors": ["stl", "gfsm", "invariants"], "fusion": fusion,
        "scenarios": scen, "all_ok": True,
    }
    (out / f"{topology}_monitor_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
    return manifest
