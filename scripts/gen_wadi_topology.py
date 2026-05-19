"""Generate a faithful, EPANET-valid data/wadi/{wadi.inp,wadi_plcs.yaml}.

Hybrid: WADI_STRUCTURE (doc-derived: WaDi.pdf + docs/table_WADI.pdf) fixes
which sensor governs which actuator + PLC/stage; thresholds are empirically
fitted from data/wadi/raw/wadi_normal.csv. Synthetic but EPANET-structurally
valid; element IDs are canonical iTrust tags. Deterministic / idempotent.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

RAW_NORMAL = Path("data/wadi/raw/wadi_normal.csv")
OUT_INP = Path("data/wadi/wadi.inp")
OUT_PLCS = Path("data/wadi/wadi_plcs.yaml")

_ACT_RE = re.compile(r"_(MV|P|SV)_\d+_STATUS$", re.I)
_SENS_RE = re.compile(r"_(LT|AIT|PIT|FIT|DPIT)_\d+_PV$", re.I)


def _canon(c: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", c.strip().lower()).strip("_")


def classify_columns(cols: list[str]) -> tuple[list[str], list[str]]:
    """Return (binary_actuators, governing_sensors), canonicalized."""
    act = [_canon(c) for c in cols if _ACT_RE.search(c.strip())]
    sens = [_canon(c) for c in cols if _SENS_RE.search(c.strip())]
    return act, sens


WADI_STRUCTURE: dict[str, dict] = {
    "1_p_001_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_p_002_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_p_003_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_p_004_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_p_005_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_p_006_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_mv_001_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_mv_002_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_mv_003_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "1_mv_004_status": {"sensor": "1_lt_001_pv", "plc": "PLC1", "stage": 1},
    "2_mv_001_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_mv_002_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_mv_003_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_mv_004_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_mv_005_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_mv_006_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_mv_009_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_p_001_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_p_002_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_p_003_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_p_004_status": {"sensor": "2_lt_002_pv", "plc": "PLC2", "stage": 2},
    "2_sv_101_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_sv_201_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_sv_301_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_sv_401_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_sv_501_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "2_sv_601_status": {"sensor": "2_lt_001_pv", "plc": "PLC2", "stage": 2},
    "3_p_001_status": {"sensor": "2_pit_001_pv", "plc": "PLC3", "stage": 3},
    "3_p_002_status": {"sensor": "2_pit_001_pv", "plc": "PLC3", "stage": 3},
    "3_p_003_status": {"sensor": "2_pit_001_pv", "plc": "PLC3", "stage": 3},
    "3_p_004_status": {"sensor": "2_pit_001_pv", "plc": "PLC3", "stage": 3},
}
DEFAULT_STAGE_SENSOR = {1: "1_lt_001_pv", 2: "2_lt_002_pv", 3: "2_pit_001_pv"}


def _minmax(col: pd.Series) -> tuple[float, float]:
    lo, hi = float(np.nanmin(col)), float(np.nanmax(col))
    return lo, (hi if hi > lo else lo + 1.0)


def fit_thresholds(df: pd.DataFrame, *, actuator: str,
                   sensor: str) -> dict | None:
    """Median governing-sensor level at the actuator's off->on and on->off
    transitions, min-max normalized to [0,1] by the sensor's own range.
    Returns None if the actuator never switches in normal data."""
    a = pd.to_numeric(df[actuator], errors="coerce").to_numpy()
    s = pd.to_numeric(df[sensor], errors="coerce").to_numpy()
    a = (a > 0.5).astype(int)
    d = np.diff(a)
    on_idx = np.where(d == 1)[0] + 1
    off_idx = np.where(d == -1)[0] + 1
    if len(on_idx) == 0 and len(off_idx) == 0:
        return None
    lo, hi = _minmax(pd.Series(s))

    def _norm(vals):
        v = s[vals]
        v = v[np.isfinite(v)]
        if len(v) == 0:
            return None
        return float(np.clip((np.median(v) - lo) / (hi - lo), 0.0, 1.0))

    on_level = _norm(on_idx) if len(on_idx) else None
    off_level = _norm(off_idx) if len(off_idx) else None
    if on_level is None and off_level is None:
        return None
    return {
        "actuator": actuator, "sensor": sensor,
        "on_level": on_level if on_level is not None else off_level,
        "off_level": off_level if off_level is not None else on_level,
        "sensor_min": lo, "sensor_max": hi,
    }
