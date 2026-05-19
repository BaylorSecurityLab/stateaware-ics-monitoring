import numpy as np
import pandas as pd

from scripts.gen_wadi_topology import fit_thresholds


def test_fit_recovers_known_hysteresis():
    # Fill-control actuator: turns ON when sensor is LOW (<0.2),
    # OFF when sensor is HIGH (>0.8). So off->on happens near 0.2
    # (on_level) and on->off near 0.8 (off_level).
    s, a, st = [], [], 0
    for k in range(2000):
        x = 0.5 + 0.5 * np.sin(k / 40.0)
        if st == 0 and x < 0.2:
            st = 1
        elif st == 1 and x > 0.8:
            st = 0
        s.append(x)
        a.append(st)
    df = pd.DataFrame({"sx": s, "ax": a})
    fit = fit_thresholds(df, actuator="ax", sensor="sx")
    assert fit is not None
    assert 0.15 < fit["on_level"] < 0.25
    assert 0.75 < fit["off_level"] < 0.85


def test_fit_returns_none_when_no_switching():
    df = pd.DataFrame({"sx": np.linspace(0, 1, 500), "ax": np.ones(500)})
    assert fit_thresholds(df, actuator="ax", sensor="sx") is None
