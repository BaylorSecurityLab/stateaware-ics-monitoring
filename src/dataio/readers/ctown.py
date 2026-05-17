"""ctown (BATADAL) raw CSV -> normalized frames. BATADAL == the C-Town network."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..schema import canonicalize_columns

DATETIME_FMT = "%d/%m/%y %H"
SOURCE_NOTE = "BATADAL is the C-Town network; renamed to ctown for repo consistency"
TEST_ATTACKS = [
    ("A8", "16/01/17 09", "19/01/17 06"),
    ("A9", "30/01/17 08", "02/02/17 00"),
    ("A10", "09/02/17 03", "10/02/17 09"),
    ("A11", "12/02/17 01", "13/02/17 07"),
    ("A12", "24/02/17 05", "28/02/17 08"),
    ("A13", "10/03/17 14", "13/03/17 21"),
    ("A14", "25/03/17 20", "27/03/17 16"),
]


def _load(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    colmap = canonicalize_columns(list(df.columns))
    df = df.rename(columns=colmap)
    df["datetime"] = pd.to_datetime(df["datetime"].astype(str).str.strip(),
                                    format=DATETIME_FMT)
    for c in df.columns:
        if c != "datetime":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, colmap


def build_normalized(raw_root: Path):
    """Return (calibration_df, eval_df_with_label, column_map, source_name)."""
    base = Path(raw_root) / "BATADAL"
    train, colmap = _load(base / "BATADAL_dataset03_train_1.csv")
    test, _ = _load(base / "BATADAL_test_dataset.csv")

    if "att_flag" in train.columns:
        clean = train[train["att_flag"] == 0].copy()
        if len(clean) < 500:
            clean = train.copy()
    else:
        clean = train.copy()
    cal = clean.drop(columns=[c for c in ("att_flag", "datetime")
                              if c in clean.columns]).reset_index(drop=True)

    y = np.zeros(len(test), dtype=int)
    for _, s, e in TEST_ATTACKS:
        sp = pd.to_datetime(s, format=DATETIME_FMT)
        ep = pd.to_datetime(e, format=DATETIME_FMT)
        y[((test["datetime"] >= sp) & (test["datetime"] <= ep)).to_numpy()] = 1
    ev = test.drop(columns=[c for c in ("att_flag", "datetime")
                            if c in test.columns]).reset_index(drop=True)
    ev["label"] = y
    return cal, ev, colmap, "BATADAL_dataset03_train_1.csv + BATADAL_test_dataset.csv"
