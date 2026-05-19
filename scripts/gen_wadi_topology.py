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


def emit_inp(fits: list[dict]) -> str:
    tanks = sorted({f["sensor"] for f in fits if "_lt_" in f["sensor"]})
    sens = sorted({f["sensor"] for f in fits})
    juncs = sorted(set(sens) - set(tanks))
    pumps = sorted(f["actuator"] for f in fits if "_p_" in f["actuator"])
    valves = sorted(f["actuator"] for f in fits
                    if "_mv_" in f["actuator"] or "_sv_" in f["actuator"])
    L = ["[TITLE]", "Faithful WADI (generated; iTrust tags; empirical CONTROLS)", ""]
    L += ["[JUNCTIONS]", ";ID\tElev\tDemand"]
    L += [f" {j}\t0\t0" for j in (juncs or ["j_dummy"])]
    L += ["", "[RESERVOIRS]", ";ID\tHead", " r_src\t100", ""]
    L += ["[TANKS]", ";ID\tElev\tInit\tMin\tMax\tDiam\tMinVol"]
    L += [f" {t}\t0\t0.5\t0\t1\t10\t0" for t in tanks]
    L += ["", "[PIPES]", ";ID\tNode1\tNode2\tLength\tDiam\tRough"]
    prev = "r_src"
    nodes = (tanks + juncs) or ["j_dummy"]
    for i, n in enumerate(nodes):
        L.append(f" pipe_{i}\t{prev}\t{n}\t100\t100\t100")
        prev = n
    L += ["", "[PUMPS]", ";ID\tNode1\tNode2\tParams"]
    L += [f" {p}\tr_src\t{nodes[0]}\tHEAD c_pump" for p in pumps]
    L += ["", "[VALVES]", ";ID\tNode1\tNode2\tDiam\tType\tSetting\tMinorLoss"]
    L += [f" {v}\tr_src\t{nodes[0]}\t100\tTCV\t0\t0" for v in valves]
    L += ["", "[CONTROLS]"]
    for f in fits:
        a, s = f["actuator"], f["sensor"]
        on, off = f["on_level"], f["off_level"]
        kind = "PUMP" if "_p_" in a else "VALVE"
        L.append(f" LINK {a} OPEN IF NODE {s} BELOW {on:.6f}")
        L.append(f" LINK {a} CLOSED IF NODE {s} ABOVE {off:.6f}")
        _ = kind
    L += ["", "[PATTERNS]", "", "[CURVES]", ";ID\tX\tY", " c_pump\t1\t50", ""]
    L += ["[RULES]", "", "[COORDINATES]", ";Node\tX\tY"]
    for i, n in enumerate(nodes + ["r_src"]):
        L.append(f" {n}\t{i}\t0")
    L += ["", "[OPTIONS]", " UNITS\tLPS", " HEADLOSS\tH-W", "", "[END]", ""]
    return "\n".join(L)


def emit_plcs(fits: list[dict]) -> list[dict]:
    by: dict[str, dict] = {}
    for f in fits:
        p = by.setdefault(f["plc"], {"name": f["plc"],
                                     "sensors": set(), "actuators": set()})
        p["sensors"].add(f["sensor"])
        p["actuators"].add(f["actuator"])
    out = []
    for name in sorted(by):
        p = by[name]
        out.append({"name": name,
                    "sensors": sorted(p["sensors"]),
                    "actuators": sorted(p["actuators"])})
    return out


def build(raw_normal: Path = RAW_NORMAL) -> tuple[str, list[dict], list[dict]]:
    df = pd.read_csv(raw_normal, low_memory=False)
    df = df.rename(columns={c: _canon(c) for c in df.columns})
    actuators, _sensors = classify_columns(list(pd.read_csv(
        raw_normal, nrows=0).columns))
    fits, manifest = [], []
    for a in sorted(set(actuators)):
        meta = WADI_STRUCTURE.get(a)
        if meta is None:
            stage = int(a[0]) if a[0] in "123" else 1
            meta = {"sensor": DEFAULT_STAGE_SENSOR[stage],
                    "plc": f"PLC{stage}", "stage": stage}
            assign = "fallback"
        else:
            assign = "doc"
        if a not in df.columns or meta["sensor"] not in df.columns:
            manifest.append({"actuator": a, "assignment": "absent"})
            continue
        ft = fit_thresholds(df, actuator=a, sensor=meta["sensor"])
        if ft is None:
            ft = {"actuator": a, "sensor": meta["sensor"],
                  "on_level": 0.25, "off_level": 0.75}
            assign += "+default-threshold"
        ft.update(plc=meta["plc"], stage=meta["stage"])
        fits.append(ft)
        manifest.append({"actuator": a, "sensor": meta["sensor"],
                         "plc": meta["plc"], "assignment": assign,
                         "on_level": ft["on_level"], "off_level": ft["off_level"]})
    return emit_inp(fits), emit_plcs(fits), manifest


def main() -> int:
    inp, plcs, manifest = build()
    OUT_INP.parent.mkdir(parents=True, exist_ok=True)
    OUT_INP.write_text(inp)
    OUT_PLCS.write_text(yaml.safe_dump(plcs, sort_keys=False))
    Path("data/wadi/wadi_topology_manifest.yaml").write_text(
        yaml.safe_dump({"actuators": manifest}, sort_keys=True))
    print(f"wrote {OUT_INP} ({len(inp.splitlines())} lines), "
          f"{OUT_PLCS} ({len(plcs)} PLCs), "
          f"{sum(1 for m in manifest if 'on_level' in m)} fitted actuators")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
