"""Stage-3 driver: dataset -> calibrate -> synthesize -> evaluate -> artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from dataio.loader import load_topology
from dataio.model import DataIoError

from .detector import StlDetector
from .manifest import build_manifest
from .metrics import detection_metrics
from .model import StlError
from .profiles import get_profile
from .synthesize import write_formulas


def run_topology(*, topology: str, data_root: Path, out_dir: Path | None,
                 jobs: int | None) -> dict[str, Any]:
    profile = get_profile(topology)
    try:
        dataset = load_topology(topology, data_root=data_root)
    except DataIoError as exc:
        raise StlError(str(exc)) from exc

    out = (Path(out_dir) if out_dir is not None
           else Path(data_root) / "generated" / topology / "stl")
    out.mkdir(parents=True, exist_ok=True)

    det = StlDetector(profile).fit(dataset.calibration_frames)
    write_formulas(det.specs, out / "stl_formulas.txt")
    (out / "calibration.json").write_text(
        json.dumps(det.params, indent=2, sort_keys=True, default=str) + "\n")

    rows, scen_status, all_ok = [], [], True
    for sc in dataset.eval_scenarios:
        flags, scores = det.predict(sc.frame, jobs=jobs)
        y = sc.labels.astype(int)
        m = detection_metrics(y, flags, scores)
        scen_status.append({"name": sc.name, "n": int(len(y)),
                            "attack_rows": int(y.sum()), "metrics": m})
        for i in range(len(y)):
            rows.append({"scenario": sc.name, "row": i, "y_true": int(y[i]),
                         "y_pred": int(flags[i]),
                         "anomaly_score": float(scores[i])})

    pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False)
    (out / "evaluation.json").write_text(
        json.dumps({"topology": topology, "scenarios": scen_status},
                   indent=2, sort_keys=True, default=str) + "\n")

    ds_man = (Path(data_root) / topology / "dataset"
              / "dataset_manifest.yaml").read_text()
    manifest = build_manifest(topology=topology, dataset_manifest_text=ds_man,
                              n_formulas=len(det.specs), scenarios=scen_status,
                              all_ok=all_ok)
    (out / f"{topology}_stl_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
