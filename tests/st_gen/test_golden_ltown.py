from .conftest import run_and_compare


def test_ltown_matches_golden(tmp_path, update_goldens):
    run_and_compare("ltown", tmp_path, update_goldens)
