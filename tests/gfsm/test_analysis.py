import pytest

from gfsm.analysis import (
    find_cycles,
    find_dead_states,
    find_unreachable_states,
    validate_references,
)
from gfsm.model import FunctionBlock, GfsmError, State, Transition


def _fb(states, edges) -> FunctionBlock:
    fb = FunctionBlock.new("FB", "s")
    for s in states:
        fb.add_state(State.new(s))
    for a, b in edges:
        fb.add_transition(Transition.new(a, b, "c"))
    return fb


def test_acyclic_has_no_cycles():
    fb = _fb(["10", "20", "30"], [("10", "20"), ("20", "30")])
    assert find_cycles(fb) == []


def test_multi_node_cycle_detected():
    fb = _fb(["10", "20", "30"],
             [("10", "20"), ("20", "30"), ("30", "10")])
    cycles = find_cycles(fb)
    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["10", "20", "30"]


def test_self_loop_detected():
    fb = _fb(["10", "20"], [("10", "20"), ("20", "20")])
    assert ["20"] in find_cycles(fb)


def test_single_node_no_self_loop_not_cycle():
    fb = _fb(["10", "20"], [("10", "20")])
    assert find_cycles(fb) == []


def test_unreachable_isolated_component():
    # Faithful Rust semantics (validator.rs:30-33): EVERY state with no
    # incoming transitions is seeded as initial, so a no-incoming state is
    # reachable by definition. A genuinely unreachable state must therefore
    # have incoming edges yet be disconnected from all initial states.
    # 10 is the only no-incoming state (initial). {50,60} form an isolated
    # cycle (each has incoming from the other, neither initial) unreachable
    # from 10. States preserve insertion order 10,20,50,60.
    fb = _fb(
        ["10", "20", "50", "60"],
        [("10", "20"), ("50", "60"), ("60", "50")],
    )
    assert find_unreachable_states(fb) == ["50", "60"]


def test_unreachable_fallback_to_100():
    fb = FunctionBlock.new("FB", "s")
    for s in ("100", "200"):
        fb.add_state(State.new(s))
    fb.add_transition(Transition.new("100", "200", "c"))
    fb.add_transition(Transition.new("200", "100", "c"))  # both have incoming
    assert find_unreachable_states(fb) == []


def test_dead_states():
    fb = _fb(["10", "20"], [("10", "20")])
    assert find_dead_states(fb) == ["20"]


def test_validate_references_ok():
    fb = _fb(["10", "20"], [("10", "20")])
    validate_references(fb)  # no raise


def test_validate_references_bad_raises():
    fb = FunctionBlock.new("FB", "s")
    fb.add_state(State.new("10"))
    fb.transitions.append(Transition.new("10", "404", "c"))
    with pytest.raises(GfsmError, match="Invalid state reference"):
        validate_references(fb)
