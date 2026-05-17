"""Top-level picklable per-PLC worker (process-pool boundary).

Returns only JSON-serializable dicts; no lxml objects cross the boundary
(required for Windows `spawn`).
"""

from __future__ import annotations

from typing import Any

from .extractor import FsmExtractor
from .model import GfsmError
from .output import fsm_to_dict


def extract_plc(name: str, ast_path: str) -> dict[str, Any]:
    try:
        fsm = FsmExtractor.from_path(ast_path).extract()
    except GfsmError as exc:
        return {
            "name": name,
            "ast_path": ast_path,
            "status": "error",
            "errors": [str(exc)],
            "counts": {},
            "fsm": None,
        }
    fb_count = len(fsm.function_blocks)
    states = sum(fb.state_count() for fb in fsm.function_blocks)
    transitions = sum(fb.transition_count() for fb in fsm.function_blocks)
    return {
        "name": name,
        "ast_path": ast_path,
        "status": "ok",
        "errors": [],
        "counts": {
            "function_blocks": fb_count,
            "states": states,
            "transitions": transitions,
        },
        "fsm": fsm_to_dict(fsm),
    }
