import importlib


def test_package_imports():
    mod = importlib.import_module("gfsm")
    assert hasattr(mod, "GfsmError")


def test_networkx_available():
    import networkx  # noqa: F401


import pytest


@pytest.mark.xfail(reason="cli.py lands in Task J1", strict=True)
def test_main_module_exposes_main():
    from gfsm.cli import main  # noqa: F401
