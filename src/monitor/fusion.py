"""Combine per-detector step flags.

fuse_or: OR of all detectors (baseline).
fuse_intersection: (any logical detector) AND (any physical detector) —
the paper's intersection of logical invariants and physical consistencies.
"""

from __future__ import annotations

import numpy as np


def fuse_or(flag_arrays: list[np.ndarray]) -> np.ndarray:
    if not flag_arrays:
        raise ValueError("fuse_or needs at least one flag array")
    out = np.zeros_like(np.asarray(flag_arrays[0]), dtype=int)
    for fa in flag_arrays:
        out = np.logical_or(out, np.asarray(fa).astype(int)).astype(int)
    return out


def fuse_intersection(logical: list[np.ndarray],
                      physical: list[np.ndarray]) -> np.ndarray:
    """Paper-faithful hybrid rule: (any logical detector fires)
    AND (any physical detector fires).

    Returns an all-zeros vector if either side has no detectors (a side
    with no evidence cannot contribute to the AND). Length is inferred
    from whichever side is non-empty; an empty result if both are empty.
    """
    if not logical or not physical:
        ref = logical or physical
        if not ref:
            return np.zeros(0, dtype=int)
        return np.zeros(len(ref[0]), dtype=int)
    lg = np.any(np.column_stack(logical), axis=1)
    ph = np.any(np.column_stack(physical), axis=1)
    return (lg & ph).astype(int)
