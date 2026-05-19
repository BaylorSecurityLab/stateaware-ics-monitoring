"""Single source of truth for evaluating Φ rules against a data row.

Owned by the `invariants` package (which defines the Φ rule schema) and
consumed by both `invariants.driver` (threshold calibration) and
`monitor.invariants_detector` (runtime). Keeping it here avoids a
layering inversion (invariants must not import monitor).
"""

from __future__ import annotations

from typing import Any

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
