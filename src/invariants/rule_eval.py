"""Single source of truth for evaluating Φ rules against a data row.

Owned by the `invariants` package (which defines the Φ rule schema) and
consumed by both `invariants.driver` (threshold calibration) and
`monitor.invariants_detector` (runtime). Keeping it here avoids a
layering inversion (invariants must not import monitor).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def atom_holds(row: pd.Series, atom: dict[str, Any]) -> bool:
    col = atom["col"]
    if col not in row.index:
        return False
    v = row[col]
    op = atom["op"]
    val = atom["val"]
    if op == "in":
        lo, hi = (val if isinstance(val, list) and len(val) == 2
                  else (None, None))
        if lo is not None and v < lo:
            return False
        if hi is not None and v > hi:
            return False
        return True
    if op == "==":
        return v == val
    if op == ">=":
        return v >= val
    if op == "<=":
        return v <= val
    if op == ">":
        return v > val
    if op == "<":
        return v < val
    return False


def all_hold(row: pd.Series, atoms: list[dict[str, Any]]) -> bool:
    return all(atom_holds(row, a) for a in atoms)


def row_violation_count(
    row: pd.Series, rules: list[dict[str, Any]]
) -> int:
    """Number of rules whose antecedent holds but consequent fails."""
    n = 0
    for r in rules:
        if all_hold(row, r.get("antecedent", [])) and not all_hold(
            row, r.get("consequent", [])
        ):
            n += 1
    return n


def _atom_mask(frame: pd.DataFrame, atom: dict[str, Any]) -> np.ndarray:
    """Vectorized atom_holds over all rows (bit-exact, incl. NaN)."""
    n = len(frame)
    col = atom["col"]
    if col not in frame.columns:
        return np.zeros(n, dtype=bool)
    s = frame[col]
    op = atom["op"]
    val = atom["val"]
    if op == "in":
        lo, hi = (val if isinstance(val, list) and len(val) == 2
                  else (None, None))
        bad = np.zeros(n, dtype=bool)
        # NOT (s>=lo)&(s<=hi): an `in` atom must HOLD on NaN (NaN<lo and
        # NaN>hi are both False), matching scalar atom_holds' </> short-
        # circuit. The >=/<= form would exclude NaN and break bit-equivalence.
        if lo is not None:
            bad = bad | (s < lo).to_numpy(dtype=bool)
        if hi is not None:
            bad = bad | (s > hi).to_numpy(dtype=bool)
        return ~bad
    if op == "==":
        return (s == val).to_numpy(dtype=bool)
    if op == ">=":
        return (s >= val).to_numpy(dtype=bool)
    if op == "<=":
        return (s <= val).to_numpy(dtype=bool)
    if op == ">":
        return (s > val).to_numpy(dtype=bool)
    if op == "<":
        return (s < val).to_numpy(dtype=bool)
    return np.zeros(n, dtype=bool)


def _all_mask(
    frame: pd.DataFrame, atoms: list[dict[str, Any]]
) -> np.ndarray:
    m = np.ones(len(frame), dtype=bool)
    for a in atoms:
        m = m & _atom_mask(frame, a)
    return m


def frame_violation_counts(
    frame: pd.DataFrame, rules: list[dict[str, Any]]
) -> np.ndarray:
    """Vectorized per-row violated-rule count over `frame`.

    Bit-identical to ``[row_violation_count(frame.iloc[i], rules) ...]``
    (pinned by a randomized equivalence test) but computed columnwise.
    """
    n = len(frame)
    counts = np.zeros(n, dtype=int)
    if n == 0 or not rules:
        return counts
    for r in rules:
        ant = _all_mask(frame, r.get("antecedent", []))
        con = _all_mask(frame, r.get("consequent", []))
        counts = counts + (ant & ~con).astype(int)
    return counts
