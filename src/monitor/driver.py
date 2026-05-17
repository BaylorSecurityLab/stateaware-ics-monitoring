"""Hybrid driver: run STL + GFSM-stub per scenario, OR the flags, write output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from dataio.loader import load_topology
from dataio.model import DataIoError
from stl.metrics import detection_metrics
from stl.profiles import get_profile

from .fusion import fuse_or
from .gfsm_detector import GfsmAnomalyDetector
from .model import MonitorError
from .stl_detector import StlAnomalyDetector


def run_topology(*, topology: str, data_root: Path, out_dir: Path | None,
                 jobs: int | None) -> dict[str, Any]:
    profile = get_profile(topology)
    try:
        dataset = load_topology(topology, data_root=data_root)
    except DataIoError as exc:
        raise MonitorError(str(exc)) from exc

    out = (Path(out_dir) if out_dir is not None
           else Path(data_root) / "generated" / topology / "monitor")
    out.mkdir(parents=True, exist_ok=True)

    stl_det = StlAnomalyDetector(profile, jobs=jobs).fit(dataset.calibration_frames)
    gfsm_det = GfsmAnomalyDetector().fit(dataset.calibration_frames)

    rows, scen = [], []
    for sc in dataset.eval_scenarios:
        s = stl_det.predict(sc.frame)
        g = gfsm_det.predict(sc.frame)
        fused = fuse_or([s.flags, g.flags])
        y = sc.labels.astype(int)
        scen.append({"name": sc.name, "n": int(len(y)),
                     "attack_rows": int(y.sum()),
                     "metrics": detection_metrics(y, fused,
                                                  s.scores if s.scores is not None
                                                  else fused.astype(float))})
        for i in range(len(y)):
            rows.append({"scenario": sc.name, "row": i, "y_true": int(y[i]),
                         "y_pred_stl": int(s.flags[i]),
                         "y_pred_gfsm": int(g.flags[i]),
                         "y_pred": int(fused[i])})

    pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False)
    manifest = {"schema": "monitor/v1", "topology": topology,
                "detectors": ["stl", "gfsm(stub)"], "fusion": "or",
                "scenarios": scen, "all_ok": True}
    (out / f"{topology}_monitor_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
    return manifest
