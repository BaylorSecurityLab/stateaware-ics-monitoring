"""Root conftest — makes 'no tests collected' exit 0 during scaffolding."""
import pytest


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Exit with code 0 when no tests are collected (scaffold phase)."""
    if exitstatus == 5:  # pytest.ExitCode.NO_TESTS_COLLECTED
        session.exitstatus = 0
