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
