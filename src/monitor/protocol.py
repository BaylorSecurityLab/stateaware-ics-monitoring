"""Hybrid-monitor detector protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd


@dataclass
class StepFlags:
    flags: np.ndarray
    scores: np.ndarray | None = None


@runtime_checkable
class AnomalyDetector(Protocol):
    name: str

    def fit(self, calibration_frames: list[pd.DataFrame]) -> "AnomalyDetector": ...

    def predict(self, frame: pd.DataFrame) -> StepFlags: ...
