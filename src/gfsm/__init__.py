"""Stage 4 — GFSM builder: faithful fsm-extractor port + synchronous composer."""

from __future__ import annotations

from .model import (
    FunctionBlock,
    GfsmError,
    GlobalFSM,
    LocalFSM,
    Metadata,
    State,
    Transition,
)

__all__ = [
    "FunctionBlock",
    "GfsmError",
    "GlobalFSM",
    "LocalFSM",
    "Metadata",
    "State",
    "Transition",
]
