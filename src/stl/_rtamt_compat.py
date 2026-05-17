"""Register a synthetic ``typing.io`` before ``rtamt``/``antlr4`` import.

antlr4-python3-runtime 4.7.2 (pulled by the git-pinned rtamt 0.4.10) does
``from typing.io import TextIO``; stdlib ``typing.io`` was removed in Python
3.12. Importing this module (idempotent) makes rtamt importable on py>=3.12.
The repo-root conftest.py applies the same shim for test sessions; this module
covers production + ProcessPool spawn workers. See INSTALL.md.
"""

from __future__ import annotations

import sys
import types
import typing

if "typing.io" not in sys.modules:
    _io_mod = types.ModuleType("typing.io")
    _io_mod.IO = typing.IO
    _io_mod.TextIO = typing.TextIO
    _io_mod.BinaryIO = typing.BinaryIO
    sys.modules["typing.io"] = _io_mod
