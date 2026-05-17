import pytest


def test_rtamt_imports_and_evaluates():
    rtamt = pytest.importorskip("rtamt")
    spec = rtamt.StlDiscreteTimeSpecification()
    spec.declare_var("x", "float")
    spec.spec = "x >= 0.0"
    spec.parse()
    res = spec.evaluate({"time": [0, 1, 2], "x": [1.0, -1.0, 2.0]})
    rob = [row[1] for row in res]
    assert rob[0] >= 0 and rob[1] < 0
