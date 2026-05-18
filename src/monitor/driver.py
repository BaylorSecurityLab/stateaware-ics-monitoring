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
from invariants.state_label import load_gfsm_components
from stl.metrics import detection_metrics
from stl.profiles import get_profile

from .fusion import fuse_intersection, fuse_or
from .gfsm_detector import GfsmAnomalyDetector
from .invariants_detector import InvariantsAnomalyDetector
from .model import MonitorError
from .stl_detector import StlAnomalyDetector


def _profile_fb_to_col(profile, components: list[tuple[str, str]]
                       ) -> dict[tuple[str, str], str]:
    """Pair gfsm-ordered components with profile.state_vars positionally.

    ORDERING CONTRACT: profile.state_vars must be declared in the same
    (plc, fb.name) ascending order gfsm.compose uses. Count mismatch is a
    hard config error.
    """
    sv = [str(v) for v in profile.state_vars]
    if len(sv) != len(components):
        raise MonitorError(
            f"{profile.name}: profile state_vars ({len(sv)}) != gfsm "
            f"components ({len(components)})"
        )
    return {c: col for c, col in zip(components, sv)}


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
    components = load_gfsm_components(json.loads(gfsm_path.read_text()))
    fb_to_col = _profile_fb_to_col(profile, components)

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
    manifest = {
        "schema": "monitor/v1", "topology": topology,
        "detectors": ["stl", "gfsm", "invariants"], "fusion": fusion,
        "scenarios": scen, "all_ok": True,
    }
    (out / f"{topology}_monitor_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
    return manifest
