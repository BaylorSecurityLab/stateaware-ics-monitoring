from .conftest import run_and_compare


def test_ctown_matches_golden(tmp_path, update_goldens):
    run_and_compare("ctown", tmp_path, update_goldens)
