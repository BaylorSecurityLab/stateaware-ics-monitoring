import numpy as np

from monitor.fusion import fuse_or


def test_fuse_or_truth_table():
    a = np.array([0, 0, 1, 1])
    b = np.array([0, 1, 0, 1])
    assert fuse_or([a, b]).tolist() == [0, 1, 1, 1]


def test_fuse_or_single():
    a = np.array([0, 1, 0])
    assert fuse_or([a]).tolist() == [0, 1, 0]
