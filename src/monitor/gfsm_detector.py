"""GFSM anomaly detector — DOCUMENTED STUB.

Stage 4's GFSM runtime detector is still being built. This conforms to the
AnomalyDetector protocol and emits all-zeros (never flags), so OR-fusion
reduces to the STL detector today. Replace `predict` with the real GFSM
state-conformance check when Stage 4's runtime lands; nothing else changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .protocol import StepFlags


class GfsmAnomalyDetector:
    name = "gfsm"

    def fit(self, calibration_frames: list[pd.DataFrame]) -> "GfsmAnomalyDetector":
        return self

    def predict(self, frame: pd.DataFrame) -> StepFlags:
        n = len(frame)
        return StepFlags(flags=np.zeros(n, dtype=int), scores=np.zeros(n))
