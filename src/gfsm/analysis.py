"""FSM analysis. Faithful port of analysis/{cycles,validator,stats}.rs.

Deterministic port deviation (hard project requirement): cycle node lists
and the list of cycles are sorted by a stable key; Rust/petgraph SCC
iteration order is unspecified and downstream output must be reproducible.
"""

from __future__ import annotations

from collections import deque

import networkx as nx

from .model import FunctionBlock


def find_cycles(fb: FunctionBlock) -> list[list[str]]:
    g = nx.MultiDiGraph()
    for sid in fb.states.keys():
        g.add_node(sid)
    for tr in fb.transitions:
        if tr.from_state in g and tr.to_state in g:
            g.add_edge(tr.from_state, tr.to_state)

    cycles: list[list[str]] = []
    for scc in nx.kosaraju_strongly_connected_components(g):
        scc = set(scc)
        if len(scc) > 1:
            cycles.append(sorted(scc))
        elif len(scc) == 1:
            node = next(iter(scc))
            if g.has_edge(node, node):
                cycles.append([node])
    cycles.sort(key=lambda c: (len(c), c))
    return cycles


def is_acyclic(fb: FunctionBlock) -> bool:
    return not find_cycles(fb)


from .model import GfsmError  # noqa: E402


def find_unreachable_states(fb: FunctionBlock) -> list[str]:
    if not fb.states:
        return []
    reachable: set[str] = set()
    queue: deque[str] = deque()
    initial = sorted([s.id for s in fb.states.values() if not s.transitions_in])
    if not initial:
        if "100" in fb.states:
            queue.append("100")
        elif fb.states:
            queue.append(next(iter(fb.states.keys())))
    else:
        queue.append(initial[0])
    while queue:
        sid = queue.popleft()
        if sid in reachable:
            continue
        reachable.add(sid)
        for tr in fb.transitions:
            if tr.from_state == sid:
                queue.append(tr.to_state)
    return [sid for sid in fb.states.keys() if sid not in reachable]


def find_dead_states(fb: FunctionBlock) -> list[str]:
    return [s.id for s in fb.states.values() if not s.transitions_out]


def validate_references(fb: FunctionBlock) -> None:
    for tr in fb.transitions:
        if tr.from_state not in fb.states:
            raise GfsmError(
                f"Invalid state reference in transition: "
                f"from_state '{tr.from_state}'"
            )
        if tr.to_state not in fb.states:
            raise GfsmError(
                f"Invalid state reference in transition: "
                f"to_state '{tr.to_state}'"
            )
