"""JSON + DOT writers. Faithful port of output/{json,dot}.rs.

JSON matches serde_json::to_string_pretty(FiniteStateMachine): 2-space
indent, struct-declaration field order, IndexMap insertion order, no key
sorting, Option::None -> null.
"""

from __future__ import annotations

import json
from typing import Any

from .model import LocalFSM


def _state_to_dict(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "transitions_out": list(s.transitions_out),
        "transitions_in": list(s.transitions_in),
    }


def _transition_to_dict(t: Any) -> dict[str, Any]:
    return {
        "id": t.id,
        "from_state": t.from_state,
        "to_state": t.to_state,
        "condition": t.condition,
        "raw_expression": t.raw_expression,
    }


def fsm_to_dict(fsm: LocalFSM) -> dict[str, Any]:
    return {
        "function_blocks": [
            {
                "name": fb.name,
                "case_variable": fb.case_variable,
                "states": {
                    sid: _state_to_dict(s) for sid, s in fb.states.items()
                },
                "transitions": [
                    _transition_to_dict(t) for t in fb.transitions
                ],
            }
            for fb in fsm.function_blocks
        ],
        "metadata": {
            "source_file": fsm.metadata.source_file,
            "extraction_date": fsm.metadata.extraction_date,
            "total_states": fsm.metadata.total_states,
            "total_transitions": fsm.metadata.total_transitions,
        },
    }


def fsm_to_json(fsm: LocalFSM) -> str:
    return json.dumps(fsm_to_dict(fsm), indent=2, ensure_ascii=False)


def fsm_to_dot(fsm: LocalFSM) -> str:
    chunks: list[str] = []
    parts: list[str] = []
    for idx, fb in enumerate(fsm.function_blocks):
        if idx > 0:
            parts.append("\n\n")
        parts.append(f'digraph "{fb.name}" {{\n')
        parts.append("    rankdir=LR;\n")
        parts.append(
            "    node [shape=circle, style=filled, fillcolor=lightblue];\n"
        )
        parts.append("    edge [fontsize=10];\n\n")
        for sid in fb.states.keys():
            parts.append(f'    "{sid}" [label="{sid}"];\n')
        parts.append("\n")
        for tr in fb.transitions:
            label = tr.condition.replace('"', '\\"').replace("\n", "\\n")
            parts.append(
                f'    "{tr.from_state}" -> "{tr.to_state}" '
                f'[label="{label}"];\n'
            )
        parts.append("}")
    chunks.append("".join(parts))
    return "".join(chunks)
