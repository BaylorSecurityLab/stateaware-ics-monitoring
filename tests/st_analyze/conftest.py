from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"


@pytest.fixture
def repo_data() -> Path:
    return DATA
