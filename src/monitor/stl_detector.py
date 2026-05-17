"""Adapt stl.detector.StlDetector to the monitor AnomalyDetector protocol."""

from __future__ import annotations

import pandas as pd

from stl.detector import StlDetector
from stl.model import TopologyProfile

from .protocol import StepFlags


class StlAnomalyDetector:
    name = "stl"

    def __init__(self, profile: TopologyProfile, jobs: int | None = None):
        self._det = StlDetector(profile)
        self._jobs = jobs

    def fit(self, calibration_frames: list[pd.DataFrame]) -> "StlAnomalyDetector":
        self._det.fit(calibration_frames)
        return self

    def predict(self, frame: pd.DataFrame) -> StepFlags:
        flags, scores = self._det.predict(frame, jobs=self._jobs)
        return StepFlags(flags=flags, scores=scores)
