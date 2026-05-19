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
