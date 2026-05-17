"""Data model and exception types for gfsm (Stage 4).

Faithful port of fsm-extractor `src/fsm/*.rs` (pinned commit 14950d5):
- State        <- src/fsm/state.rs
- Transition   <- src/fsm/transition.rs
- FunctionBlock<- src/fsm/function_block.rs
- LocalFSM     <- src/fsm/mod.rs FiniteStateMachine
- Metadata     <- src/fsm/mod.rs Metadata
GlobalFSM and GfsmError are new (composer support).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class GfsmError(Exception):
    """Raised for unrecoverable Stage-4 errors (bad XML, overflow, etc.)."""


@dataclass
class State:
    """Port of src/fsm/state.rs State."""

    id: str
    name: str | None = None
    transitions_out: list[str] = field(default_factory=list)
    transitions_in: list[str] = field(default_factory=list)

    @classmethod
    def new(cls, id: str) -> "State":
        return cls(id=id, name=None, transitions_out=[], transitions_in=[])


@dataclass
class Transition:
    """Port of src/fsm/transition.rs Transition."""

    id: str
    from_state: str
    to_state: str
    condition: str
    raw_expression: str

    @classmethod
    def new(cls, from_state: str, to_state: str, condition: str) -> "Transition":
        return cls(
            id=f"{from_state}_to_{to_state}",
            from_state=from_state,
            to_state=to_state,
            condition=condition,
            raw_expression=condition,
        )


@dataclass
class FunctionBlock:
    """Port of src/fsm/function_block.rs FunctionBlock.

    `states` is a plain dict; Python dicts are insertion-ordered, matching
    Rust `IndexMap` iteration order used everywhere downstream.
    """

    name: str
    case_variable: str
    states: dict[str, State] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)

    @classmethod
    def new(cls, name: str, case_variable: str) -> "FunctionBlock":
        return cls(name=name, case_variable=case_variable, states={}, transitions=[])

    def add_state(self, state: State) -> None:
        # IndexMap::insert overwrites; dict assignment matches.
        self.states[state.id] = state

    def add_transition(self, transition: Transition) -> None:
        # function_block.rs:28-37 — update refs only if endpoint exists.
        from_state = self.states.get(transition.from_state)
        if from_state is not None:
            from_state.transitions_out.append(transition.id)
        to_state = self.states.get(transition.to_state)
        if to_state is not None:
            to_state.transitions_in.append(transition.id)
        self.transitions.append(transition)

    def get_state(self, id: str) -> State | None:
        return self.states.get(id)

    def state_count(self) -> int:
        return len(self.states)

    def transition_count(self) -> int:
        return len(self.transitions)


@dataclass
class Metadata:
    """Port of src/fsm/mod.rs Metadata. extraction_date is an ISO-8601 str."""

    source_file: str
    extraction_date: str
    total_states: int
    total_transitions: int


@dataclass
class LocalFSM:
    """Port of src/fsm/mod.rs FiniteStateMachine (one .ast.xml file)."""

    function_blocks: list[FunctionBlock] = field(default_factory=list)
    metadata: Metadata | None = None


@dataclass
class GlobalFSM:
    """NEW — composed synchronous-product automaton (compose.py)."""

    states: dict[str, tuple[str, ...]]
    transitions: list[dict[str, Any]]
    initial: str
    metadata: Metadata
    max_states: int
