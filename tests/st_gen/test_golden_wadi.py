from .conftest import run_and_compare


def test_wadi_matches_golden(tmp_path, update_goldens):
    run_and_compare("wadi", tmp_path, update_goldens)
