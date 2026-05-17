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


def _encode(comps: list[Component], local_ids: tuple[str, ...]) -> str:
    return "|".join(f"{c.plc}:{sid}" for c, sid in zip(comps, local_ids))


def _component_choices(
    fb: FunctionBlock, current: str
) -> list[tuple[str, str | None, list[list[Condition]]]]:
    """Viable outgoing transitions from `current`, else a single stutter.

    Returns list of (target_state, transition_id|None, guard_dnf).
    Stutter is encoded as (current, None, [[]]) — guard TRUE, no move.
    """
    viable: list[tuple[str, str | None, list[list[Condition]]]] = []
    for tr in fb.transitions:
        if tr.from_state != current:
            continue
        dnf = parse_transition_condition(tr.condition)
        if is_syntactically_unsat(dnf):
            continue
        viable.append((tr.to_state, tr.id, dnf))
    if not viable:
        return [(current, None, [[]])]
    return viable
