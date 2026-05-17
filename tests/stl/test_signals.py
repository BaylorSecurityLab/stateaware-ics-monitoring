import numpy as np
import pandas as pd

from stl.profiles import CTOWN
from stl.signals import build_signals


def test_build_signals_derives_diffs():
    df = pd.DataFrame({"l_t1": [1.0, 2.0, 4.0], "s_pu1": [0.0, 1.0, 1.0]})
    params = {"mb": {}, "mb_window": {}}
    sig = build_signals(CTOWN, df, params)
    assert sig["time"] == [0, 1, 2]
    assert sig["l_t1"] == [1.0, 2.0, 4.0]
    assert np.allclose(sig["dl_t1"], [0.0, 1.0, 2.0])
