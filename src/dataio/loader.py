"""Load the committed normalized dataset into a typed TopologyDataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .manifest import load_dataset_manifest
from .model import DataIoError, DatasetSchema, Scenario, TopologyDataset


def _schema_from_columns(topology: str, columns: list[str],
                         column_map: dict[str, str]) -> DatasetSchema:
    cols = [c for c in columns if c != "label"]
    tank = [c for c in cols if c.startswith(("t", "l_t")) and "_pu" not in c]
    pstat = [c for c in cols if c.startswith(("s_pu", "pump_", "p7", "p8"))
             and not c.startswith("p_j")]
    pflow = [c for c in cols if c.startswith(("f_pu", "f_p", "f_pump"))]
    junc = [c for c in cols if c.startswith(("p_j", "n"))]
    return DatasetSchema(
        topology=topology, tank_cols=tank, pump_status_cols=pstat,
        pump_flow_cols=pflow, junction_cols=junc, column_map=dict(column_map),
    )


def load_topology(topology: str, data_root: Path = Path("data")) -> TopologyDataset:
    ds = Path(data_root) / topology / "dataset"
    man_path = ds / "dataset_manifest.yaml"
    if not man_path.exists():
        raise DataIoError(f"no normalized dataset for {topology}: {man_path} "
                          f"missing (run dataio-ingest)")
    man = load_dataset_manifest(man_path)

    cal_frames = [pd.read_csv(ds / rel) for rel in man["files"]["calibration"]]
    if not cal_frames:
        raise DataIoError(f"{topology}: dataset manifest lists no calibration files")

    scenarios: list[Scenario] = []
    for rel in man["files"]["evaluation"]:
        df = pd.read_csv(ds / rel)
        if "label" not in df.columns:
            raise DataIoError(f"{topology}: {rel} has no 'label' column")
        labels = df["label"].astype(int).to_numpy()
        frame = df.drop(columns=["label"]).reset_index(drop=True)
        windows = [(w["id"], w["start"], w["end"])
                   for w in man.get("attack_windows", [])]
        scenarios.append(Scenario(name=Path(rel).stem, frame=frame,
                                   labels=labels, attack_windows=windows))

    all_cols = list(cal_frames[0].columns)
    schema = _schema_from_columns(topology, all_cols, man.get("column_map", {}))
    return TopologyDataset(topology=topology, calibration_frames=cal_frames,
                           eval_scenarios=scenarios, schema=schema)
