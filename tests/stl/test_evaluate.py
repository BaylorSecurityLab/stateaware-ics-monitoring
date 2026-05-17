import numpy as np
import pytest

pytest.importorskip("rtamt")

from stl.evaluate import evaluate_stl_batch, vars_in, min_robustness


def test_vars_in_excludes_reserved():
    assert vars_in("abs(x - y) <= 1.0 and z >= 0") == ["x", "y", "z"]


def _signals(n=6):
    return {"time": list(range(n)),
            "x": [1.0, -1.0, 2.0, -3.0, 0.5, -0.5],
            "y": [0.0] * n}


def test_evaluate_jobs1_equals_jobs4_byte_identical():
    specs = {f"F{i}": f"x >= {i - 2}.0" for i in range(12)}
    sig = _signals()
    a = evaluate_stl_batch(specs, sig, jobs=1)
    b = evaluate_stl_batch(specs, sig, jobs=4)
    assert sorted(a) == sorted(b)
    for k in a:
        assert np.array_equal(a[k], b[k]), k
    rmin_a, arg_a = min_robustness(a, len(sig["time"]))
    rmin_b, arg_b = min_robustness(b, len(sig["time"]))
    assert np.array_equal(rmin_a, rmin_b)
    assert (arg_a == arg_b).all()
