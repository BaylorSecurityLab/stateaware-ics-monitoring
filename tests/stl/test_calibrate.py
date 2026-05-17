import numpy as np
import pandas as pd

from stl.profiles import CTOWN
from stl.calibrate import calibrate


def test_calibrate_tank_bounds_and_keys():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "l_t1": rng.uniform(1.0, 5.0, 2000),
        "s_pu1": rng.integers(0, 2, 2000).astype(float),
        "f_pu1": rng.uniform(0, 10, 2000),
    })
    p = calibrate(CTOWN, df)
    assert set(p) >= {"mb", "mb_window", "tank", "pump", "valve",
                      "head", "pressure", "pslew", "symmetry"}
    assert "l_t1" in p["tank"]
    tb = p["tank"]["l_t1"]
    assert tb["h_min"] <= df["l_t1"].min()
    assert tb["h_max"] >= df["l_t1"].max()
