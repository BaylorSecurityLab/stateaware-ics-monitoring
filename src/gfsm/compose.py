"""NEW — synchronous+stutter product automaton (spec §6).

Not ported from Rust (fsm-extractor has no composition). Deterministic by
construction: components sorted by (plc, function_block), BFS frontier is a
FIFO, global-state ids are canonical strings.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .model import FunctionBlock, GfsmError, GlobalFSM, LocalFSM, Metadata
from .signatures import Condition, is_syntactically_unsat, parse_transition_condition

DEFAULT_MAX_STATES = 100_000


@dataclass(frozen=True)
class Component:
    plc: str
    fb: FunctionBlock


def _ordered_components(fsms: dict[str, LocalFSM]) -> list[Component]:
    comps: list[Component] = []
    for plc, lf in fsms.items():
        for fb in lf.function_blocks:
            comps.append(Component(plc, fb))
    comps.sort(key=lambda c: (c.plc, c.fb.name))
    return comps


def _component_initial(fb: FunctionBlock) -> str:
    for s in fb.states.values():
        if not s.transitions_in:
            return s.id
    if "100" in fb.states:
        return "100"
    if fb.states:
        return next(iter(fb.states.keys()))
    raise GfsmError(f"function block '{fb.name}' has no states")
