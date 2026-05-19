"""Pure selection of the Φ violation threshold K from clean data.

K = smallest integer k >= 1 such that the clean-calibration flag-rate
    mean( state_absent OR violated_rule_count >= k )  <=  budget τ.
If no k in [1, max_count+1] achieves τ (state-absent rate alone exceeds
τ), K = max_count + 1 and a human-readable note is returned (surfaced,
not silent).
"""

from __future__ import annotations

import numpy as np


def select_violation_threshold(
    counts: np.ndarray, absent: np.ndarray, budget: float
) -> tuple[int, str | None]:
    if not (0.0 < budget < 1.0):
        raise ValueError(
            f"fp-budget must be in (0, 1), got {budget!r}")
    counts = np.asarray(counts).astype(int)
    absent = np.asarray(absent).astype(bool)
    n = len(counts)
    if n == 0:
        return 1, None
    max_count = int(counts.max())
    for k in range(1, max_count + 2):
        rate = float(np.mean(absent | (counts >= k)))
        if rate <= budget:
            return k, None
    k = max_count + 1
    rate = float(np.mean(absent | (counts >= k)))  # == mean(absent)
    return k, (
        f"budget unmet: clean flag-rate {rate:.4f} > budget {budget} "
        f"even at K={k} (state-absent rate alone exceeds budget; "
        f"rule-flagging effectively disabled, state-absent still flags)"
    )
