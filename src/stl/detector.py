"""Offline-batch STL anomaly detector: fit -> calibrate+synthesize, predict -> flags."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .calibrate import calibrate, calibrate_mb_pooled
from .evaluate import evaluate_stl_batch
from .metrics import hysteresis_filter
from .model import TopologyProfile
from .signals import build_signals
from .synthesize import synthesize


class StlDetector:
    def __init__(self, profile: TopologyProfile):
        self.profile = profile
        self.params: dict | None = None
        self.specs: dict[str, str] = {}

    def fit(self, calibration_frames: list[pd.DataFrame]) -> "StlDetector":
        cal_df = pd.concat(calibration_frames, ignore_index=True)
        params = calibrate(self.profile, cal_df)
        if self.profile.feeder_map:
            mb, mbw = calibrate_mb_pooled(self.profile, calibration_frames)
            params["mb"], params["mb_window"] = mb, mbw
        self.params = params
        self.specs = synthesize(self.profile, params)
        return self

    def predict(self, frame: pd.DataFrame, jobs: int | None = None):
        if self.params is None:
            raise RuntimeError("StlDetector.predict called before fit")
        n = len(frame)
        sig = build_signals(self.profile, frame, self.params)
        rob = evaluate_stl_batch(self.specs, sig, jobs=jobs)
        count_fire = np.zeros(n)
        for name in sorted(rob):
            count_fire += (np.asarray(rob[name]) < 0).astype(float)
        k = self.profile.min_fire_count
        raw = (count_fire >= k).astype(int)
        confirmed = hysteresis_filter(-(raw.astype(float)),
                                      self.profile.hysteresis)
        scores = (pd.Series(count_fire)
                  .rolling(self.profile.smoothing_window, min_periods=1,
                           center=True).max().to_numpy())
        return confirmed.astype(int), scores
