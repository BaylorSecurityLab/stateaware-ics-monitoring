import numpy as np
import pandas as pd
import pytest

pytest.importorskip("rtamt")

from stl.profiles import CTOWN
from stl.detector import StlDetector


def test_fit_predict_flags_out_of_range():
    rng = np.random.default_rng(1)
    cal = pd.DataFrame({"l_t1": rng.uniform(2.0, 3.0, 1500)})
    det = StlDetector(CTOWN)
    det.fit([cal])
    assert det.specs
    test = pd.DataFrame({"l_t1": [2.5] * 5 + [999.0] * 5})
    flags, scores = det.predict(test)
    assert flags.shape == (10,)
    assert flags[5:].sum() >= 1
