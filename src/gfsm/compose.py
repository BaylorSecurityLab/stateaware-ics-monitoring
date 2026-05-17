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


def _conjoin_dnf(dnfs: list[list[list[Condition]]]) -> list[list[Condition]]:
    """Cross-product conjunction of several DNFs. [] -> [[ ]] (TRUE)."""
    result: list[list[Condition]] = [[]]
    for dnf in dnfs:
        if not dnf:
            dnf = [[]]
        new_result: list[list[Condition]] = []
        for lt in result:
            for rt in dnf:
                new_result.append([*lt, *rt])
        result = new_result
    return result if result else [[]]


def _global_guard_str(dnf: list[list[Condition]]) -> str:
    """Serialize a DNF guard to a canonical string.

    Each conjunction's conditions are sorted by (variable, operator, value)
    and joined with " AND " (an empty conjunction = "TRUE"). Disjuncts are
    deduped preserving first-seen order and joined with " OR ". A guard that
    is purely TRUE returns "TRUE".
    """
    terms: list[str] = []
    for conj in dnf:
        if not conj:
            terms.append("TRUE")
            continue
        ordered = sorted(
            conj, key=lambda c: (c.variable, c.operator, c.value)
        )
        terms.append(" AND ".join(c.to_string() for c in ordered))
    uniq = list(dict.fromkeys(terms))
    if uniq == ["TRUE"]:
        return "TRUE"
    return " OR ".join(uniq)
