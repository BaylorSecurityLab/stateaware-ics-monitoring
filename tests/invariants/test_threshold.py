import numpy as np
import pytest

from invariants.threshold import select_violation_threshold


def test_smallest_k_meeting_budget():
    counts = np.array([0, 0, 0, 0, 0, 2, 2, 2, 5, 5])
    absent = np.zeros(10, dtype=bool)
    k, note = select_violation_threshold(counts, absent, 0.20)
    assert k == 3 and note is None


def test_monotonic_larger_budget_gives_smaller_or_equal_k():
    counts = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    absent = np.zeros(10, dtype=bool)
    k_strict, _ = select_violation_threshold(counts, absent, 0.10)
    k_loose, _ = select_violation_threshold(counts, absent, 0.50)
    assert k_loose <= k_strict


def test_budget_unmet_due_to_state_absent_rate():
    counts = np.array([0, 0, 0, 0])
    absent = np.array([True, True, False, False])
    k, note = select_violation_threshold(counts, absent, 0.10)
    assert k == 1
    assert note is not None and "budget unmet" in note


def test_invalid_budget_raises():
    with pytest.raises(ValueError):
        select_violation_threshold(np.array([0]), np.array([False]), 0.0)
    with pytest.raises(ValueError):
        select_violation_threshold(np.array([0]), np.array([False]), 1.0)
