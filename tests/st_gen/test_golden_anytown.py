from .conftest import run_and_compare


def test_anytown_matches_golden(tmp_path, update_goldens):
    run_and_compare("anytown", tmp_path, update_goldens)
