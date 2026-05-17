import numpy as np

from monitor.fusion import fuse_intersection


def test_intersection_truth_table():
    L1 = np.array([0, 0, 1, 1])
    L2 = np.array([0, 1, 0, 1])
    P = np.array([1, 1, 1, 1])
    # logical = L1|L2 = [0,1,1,1]; physical = [1,1,1,1]; AND = [0,1,1,1]
    assert (fuse_intersection([L1, L2], [P]) == np.array([0, 1, 1, 1])).all()


def test_intersection_zero_when_physical_silent():
    L = np.array([1, 1, 1])
    P = np.array([0, 0, 0])
    assert (fuse_intersection([L], [P]) == np.zeros(3, dtype=int)).all()


def test_intersection_empty_inputs():
    assert (fuse_intersection([], [np.array([1, 1])])
            == np.zeros(2, dtype=int)).all()
    assert (fuse_intersection([np.array([1, 1])], [])
            == np.zeros(2, dtype=int)).all()
    assert fuse_intersection([], []).shape == (0,)
