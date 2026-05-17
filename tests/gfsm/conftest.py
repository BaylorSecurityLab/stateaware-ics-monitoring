from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
GEN = DATA / "generated"


@pytest.fixture
def repo_data() -> Path:
    return DATA


@pytest.fixture
def gen_dir() -> Path:
    return GEN
