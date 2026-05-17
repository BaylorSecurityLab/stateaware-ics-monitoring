import numpy as np
import pandas as pd

from monitor.gfsm_detector import GfsmAnomalyDetector
from monitor.protocol import AnomalyDetector


def test_gfsm_stub_is_all_zeros_and_conforms():
    det = GfsmAnomalyDetector()
    assert isinstance(det, AnomalyDetector)
    det.fit([pd.DataFrame({"x": [1.0, 2.0]})])
    out = det.predict(pd.DataFrame({"x": [1.0, 2.0, 3.0]}))
    assert out.flags.tolist() == [0, 0, 0]
