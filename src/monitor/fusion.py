"""Combine per-detector step flags. Final label = logical OR."""

from __future__ import annotations

import numpy as np


def fuse_or(flag_arrays: list[np.ndarray]) -> np.ndarray:
    if not flag_arrays:
        raise ValueError("fuse_or needs at least one flag array")
    out = np.zeros_like(np.asarray(flag_arrays[0]), dtype=int)
    for fa in flag_arrays:
        out = np.logical_or(out, np.asarray(fa).astype(int)).astype(int)
    return out
