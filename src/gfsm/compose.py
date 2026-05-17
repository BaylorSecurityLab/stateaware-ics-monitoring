"""NEW — synchronous+stutter product automaton (spec §6).

Not ported from Rust (fsm-extractor has no composition). Deterministic by
construction: components sorted by (plc, function_block), BFS frontier is a
FIFO, global-state ids are canonical strings.
"""

from __future__ import annotations

import itertools
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


def compose_global(
    fsms: dict[str, LocalFSM],
    *,
    max_states: int = DEFAULT_MAX_STATES,
    source_file: str = "<composed>",
) -> GlobalFSM:
    """Build the synchronous+stutter product automaton (spec §6, semantics B).

    Composes the given per-PLC ``LocalFSM`` components into a single
    ``GlobalFSM`` via BFS over reachable global states, allowing joint moves
    and single-mover interleavings (a component with viable moves may also
    stutter). The result is reachable-only and deterministic by construction.

    :param fsms: mapping of PLC name to its ``LocalFSM``.
    :param max_states: keyword-only cap on the reachable-state set size.
    :param source_file: metadata provenance string recorded on the result.
    :returns: a ``GlobalFSM`` containing only reachable states, deterministic.
    :raises GfsmError: if the input is empty ("no function blocks to compose")
        or the reachable state set would exceed ``max_states`` (state
        explosion).
    """
    comps = _ordered_components(fsms)
    if not comps:
        raise GfsmError("no function blocks to compose")

    init_local = tuple(_component_initial(c.fb) for c in comps)
    init_id = _encode(comps, init_local)

    states: dict[str, tuple[str, ...]] = {init_id: init_local}
    transitions: list[dict[str, Any]] = []
    seen_tr: set[tuple[str, str, str]] = set()

    frontier: deque[tuple[str, tuple[str, ...]]] = deque()
    frontier.append((init_id, init_local))

    while frontier:
        cur_id, cur_local = frontier.popleft()

        per_comp_choices = []
        for i, c in enumerate(comps):
            cc = _component_choices(c.fb, cur_local[i])
            # Semantics B (spec §6, user-confirmed): a component with viable
            # moves may ALSO stutter, so single-mover interleavings exist
            # alongside joint moves. When no real move exists,
            # _component_choices already returns the stutter sentinel as the
            # sole choice; appending it again would double-count and yield a
            # spurious all-stutter combo, so only augment when a real move
            # (tid is not None) is present.
            if any(tid is not None for _t, tid, _d in cc):
                cc = cc + [(cur_local[i], None, [[]])]
            per_comp_choices.append(cc)

        for combo in itertools.product(*per_comp_choices):
            # combo[i] = (target, tid_or_None, dnf)
            if all(tid is None for _t, tid, _d in combo):
                continue  # all-stutter step dropped

            moving_dnfs = [
                dnf for _t, tid, dnf in combo if tid is not None
            ]
            guard_dnf = _conjoin_dnf(moving_dnfs)
            if is_syntactically_unsat(guard_dnf):
                continue

            next_local = tuple(t for t, _tid, _d in combo)
            next_id = _encode(comps, next_local)

            if next_id not in states:
                if len(states) + 1 > max_states:
                    raise GfsmError(
                        f"global FSM exceeds --max-states={max_states} "
                        f"(state explosion); aborting"
                    )
                states[next_id] = next_local
                frontier.append((next_id, next_local))

            provenance = {
                f"{c.plc}:{c.fb.name}": tid
                for c, (_t, tid, _d) in zip(comps, combo)
            }
            guard = _global_guard_str(guard_dnf)
            key = (cur_id, next_id, guard)
            if key in seen_tr:
                continue
            seen_tr.add(key)
            transitions.append({
                "id": f"{cur_id}=>{next_id}",
                "from": cur_id,
                "to": next_id,
                "guard": guard,
                "components": provenance,
            })

    transitions.sort(key=lambda t: (t["from"], t["to"], t["guard"]))
    md = Metadata(
        source_file=source_file,
        extraction_date=datetime.now(timezone.utc).isoformat(),
        total_states=len(states),
        total_transitions=len(transitions),
    )
    return GlobalFSM(
        states=states,
        transitions=transitions,
        initial=init_id,
        metadata=md,
        max_states=max_states,
    )


from .model import State, Transition  # noqa: E402


def global_as_function_block(g: GlobalFSM) -> FunctionBlock:
    """Wrap a GlobalFSM as a FunctionBlock for Phase-D analysis reuse."""
    fb = FunctionBlock.new("__global__", "__global__")
    for sid in g.states.keys():
        fb.add_state(State.new(sid))
    for t in g.transitions:
        tr = Transition(
            id=t["id"],
            from_state=t["from"],
            to_state=t["to"],
            condition=t["guard"],
            raw_expression=t["guard"],
        )
        fb.add_transition(tr)
    return fb
