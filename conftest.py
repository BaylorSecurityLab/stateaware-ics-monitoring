"""Repo-root pytest bootstrap.

Registers a synthetic ``typing.io`` module before any test imports ``rtamt``.
``rtamt`` (installed from git, 0.4.10) depends on ``antlr4-python3-runtime``
4.7.2, whose ``Lexer`` does ``from typing.io import TextIO``. The stdlib
``typing.io`` pseudo-module was removed in Python 3.12, so on this project's
Python (>=3.13) that import fails. ``typing.IO/TextIO/BinaryIO`` still exist,
so we expose them under the legacy ``typing.io`` name. See INSTALL.md.

The production runtime applies the same shim via ``stl._rtamt_compat`` (imported
before ``rtamt`` in ``stl.evaluate``); this conftest covers the test session.
"""

import sys
import types
import typing

if "typing.io" not in sys.modules:
    _io_mod = types.ModuleType("typing.io")
    _io_mod.IO = typing.IO
    _io_mod.TextIO = typing.TextIO
    _io_mod.BinaryIO = typing.BinaryIO
    sys.modules["typing.io"] = _io_mod
