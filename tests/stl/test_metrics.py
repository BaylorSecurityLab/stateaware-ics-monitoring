import numpy as np

from stl.metrics import hysteresis_filter, detection_metrics


def test_hysteresis_requires_k_consecutive():
    rob = np.array([-1.0, 0.5, -1.0, -1.0, -1.0, 0.5])
    out = hysteresis_filter(rob, 2)
    assert out.tolist() == [0, 0, 1, 1, 1, 0]


def test_detection_metrics_perfect():
    y = np.array([0, 0, 1, 1])
    m = detection_metrics(y, y, y.astype(float))
    assert m["recall"] == 1.0 and m["precision"] == 1.0
    assert m["tp"] == 2 and m["fp"] == 0
