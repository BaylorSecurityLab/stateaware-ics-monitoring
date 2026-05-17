"""anytown raw 7z dataset -> normalized calibration/eval frames (port of anytown_detect.py)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..schema import canonicalize_columns

SOURCE_NAME = "anytown_dataset.zip"

EVAL_SCENARIOS = {
    "1 - MiTM": (649, 794, "mitm"),
    "3 - DoS": (649, 794, "dos"),
}
CALIB_PRE_TRIGGER_END = 648


def _ensure_extracted(zip_path: Path, extract_parent: Path, extracted: Path) -> None:
    sentinel = (
        extracted
        / "disruptive_anomalies_and_attacks"
        / "1 - MiTM"
        / "output"
        / "scada_values.csv"
    )
    if sentinel.exists():
        return
    import py7zr  # noqa: PLC0415 — lazy import; module must not require py7zr at import time

    extract_parent.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(str(zip_path), "r") as z:
        names = z.getnames()
    targets = [
        n
        for n in names
        if n.endswith((".csv", ".yaml", ".md", ".inp", ".txt", ".json"))
    ]
    with py7zr.SevenZipFile(str(zip_path), "r") as z:
        z.extract(path=str(extract_parent), targets=targets)


def _load_scada(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df["DATETIME"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.drop(columns=["timestamp"])
    for c in df.columns:
        if c != "DATETIME":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["iteration"] > 0].reset_index(drop=True)
    for c in df.columns:
        if c == "DATETIME":
            continue
        df[c] = df[c].ffill().bfill()
    return df


def _load_ground_truth(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    return df


def _pool_calibration(extracted: Path) -> list[pd.DataFrame]:
    cal_root = extracted / "network_anomalies"
    paths = sorted(cal_root.rglob("scada_values.csv"))
    frames: list[pd.DataFrame] = []
    for p in paths:
        try:
            df = _load_scada(p)
            df = df[df["iteration"] < CALIB_PRE_TRIGGER_END].reset_index(drop=True)
            if len(df) > 0:
                df = df.drop(columns=["DATETIME"], errors="ignore")
                col_map = canonicalize_columns(list(df.columns))
                df = df.rename(columns=col_map)
                frames.append(df)
        except Exception:
            pass
    return frames


def _load_eval_scenario(
    extracted: Path,
    sub: str,
    trigger_start: int,
    trigger_end: int,
) -> pd.DataFrame | None:
    scenario_dir = extracted / "disruptive_anomalies_and_attacks" / sub / "output"
    scada_path = scenario_dir / "scada_values.csv"
    gt_path = scenario_dir / "ground_truth.csv"

    if not scada_path.exists():
        return None

    scada = _load_scada(scada_path)
    gt = _load_ground_truth(gt_path)

    if "plc1attack" in gt.columns:
        labels = gt[["iteration", "plc1attack"]].copy()
    else:
        labels = gt[["iteration"]].copy()
        labels["plc1attack"] = (
            (gt["iteration"] >= trigger_start) & (gt["iteration"] < trigger_end)
        ).astype(int)

    merged = scada.merge(labels, on="iteration", how="inner").reset_index(drop=True)

    # Build column_map BEFORE renaming (raw scada cols, excluding DATETIME)
    raw_cols = [c for c in merged.columns if c not in ("DATETIME", "plc1attack")]

    # Drop DATETIME before canonicalization
    merged = merged.drop(columns=["DATETIME"], errors="ignore")

    # Rename plc1attack -> label before canonicalization
    merged = merged.rename(columns={"plc1attack": "label"})

    # Canonicalize all columns except label
    non_label_cols = [c for c in merged.columns if c != "label"]
    col_map = canonicalize_columns(non_label_cols)
    merged = merged.rename(columns=col_map)

    merged["label"] = merged["label"].astype(int)

    return merged, raw_cols, col_map


def build_normalized(
    raw_root: Path,
) -> tuple[
    list[pd.DataFrame],
    list[tuple[str, pd.DataFrame]],
    dict[str, str],
    str,
]:
    """Return (calibration_frames, eval_named, column_map, source_name).

    Raw 7z source: <raw_root>/Anytown/anytown_dataset.zip
    """
    raw_root = Path(raw_root)
    anytown_data = raw_root / "Anytown"
    zip_path = anytown_data / "anytown_dataset.zip"
    extract_parent = anytown_data / "_inspect"
    extracted = extract_parent / "anytown_dataset"

    _ensure_extracted(zip_path, extract_parent, extracted)

    calibration_frames = _pool_calibration(extracted)

    eval_named: list[tuple[str, pd.DataFrame]] = []
    union_raw: list[str] = []
    union_col_map: dict[str, str] = {}

    for sub, (trigger_start, trigger_end, name) in EVAL_SCENARIOS.items():
        result = _load_eval_scenario(extracted, sub, trigger_start, trigger_end)
        if result is None:
            continue
        df, raw_cols, col_map = result
        eval_named.append((name, df))
        for rc in raw_cols:
            if rc not in union_col_map:
                union_col_map[rc] = col_map.get(rc, rc)

    return calibration_frames, eval_named, union_col_map, SOURCE_NAME
