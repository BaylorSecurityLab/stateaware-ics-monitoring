from gfsm.compose import (
    Component,
    _component_choices,
    _component_initial,
    _conjoin_dnf,
    _encode,
    _global_guard_str,
    _ordered_components,
)
from gfsm.model import FunctionBlock, LocalFSM, Metadata, State, Transition
from gfsm.signatures import Condition


def _fb(name, states, edges, case="S") -> FunctionBlock:
    fb = FunctionBlock.new(name, case)
    for s in states:
        fb.add_state(State.new(s))
    for a, b, c in edges:
        fb.add_transition(Transition.new(a, b, c))
    return fb


def test_ordering_by_plc_then_fb():
    a = _fb("FBb", ["10"], [])
    b = _fb("FBa", ["10"], [])
    m = Metadata("s", "t", 0, 0)
    fsms = {
        "plcB": LocalFSM([a], m),
        "plcA": LocalFSM([b], m),
    }
    comps = _ordered_components(fsms)
    assert [(c.plc, c.fb.name) for c in comps] == [
        ("plcA", "FBa"), ("plcB", "FBb")
    ]


def test_component_initial_no_incoming():
    fb = _fb("FB", ["10", "20"], [("10", "20", "c")])
    assert _component_initial(fb) == "10"


def test_component_initial_fallback_100():
    fb = FunctionBlock.new("FB", "S")
    fb.add_state(State.new("100"))
    fb.add_state(State.new("200"))
    fb.add_transition(Transition.new("100", "200", "c"))
    fb.add_transition(Transition.new("200", "100", "c"))
    assert _component_initial(fb) == "100"


def test_encode_is_canonical():
    a = _fb("A", ["10"], [])
    b = _fb("B", ["20"], [])
    m = Metadata("s", "t", 0, 0)
    comps = _ordered_components({"p2": LocalFSM([b], m), "p1": LocalFSM([a], m)})
    assert _encode(comps, ("10", "20")) == "p1:10|p2:20"


def test_component_choices_includes_viable_and_excludes_unsat():
    fb = _fb(
        "A",
        ["10", "20", "30"],
        [
            ("10", "20", "x > 5 AND x < 3"),  # unsat -> excluded
            ("10", "30", "y = 1"),  # viable
        ],
    )
    choices = _component_choices(fb, "10")
    # Each choice: (target_state, transition_id_or_None, dnf)
    targets = sorted(t for t, _tid, _dnf in choices)
    assert "30" in targets
    assert "20" not in targets


def test_component_choices_stutter_when_no_viable():
    fb = _fb("A", ["10", "20"], [("10", "20", "x > 5 AND x < 3")])
    choices = _component_choices(fb, "10")
    assert choices == [("10", None, [[]])]  # stutter only


def test_conjoin_cross_product():
    d1 = [[Condition("A", "=", "1")]]
    d2 = [[Condition("B", "=", "2")], [Condition("B", "=", "3")]]
    out = _conjoin_dnf([d1, d2])
    assert out == [
        [Condition("A", "=", "1"), Condition("B", "=", "2")],
        [Condition("A", "=", "1"), Condition("B", "=", "3")],
    ]


def test_conjoin_empty_is_true():
    assert _conjoin_dnf([]) == [[]]
    assert _conjoin_dnf([[[]]]) == [[]]


def test_conjoin_three_dnfs():
    d1 = [[Condition("A", "=", "1")]]
    d2 = [[Condition("B", "=", "2")]]
    d3 = [[Condition("C", "=", "3")], [Condition("C", "=", "4")]]
    assert _conjoin_dnf([d1, d2, d3]) == [
        [Condition("A", "=", "1"), Condition("B", "=", "2"),
         Condition("C", "=", "3")],
        [Condition("A", "=", "1"), Condition("B", "=", "2"),
         Condition("C", "=", "4")],
    ]


def test_global_guard_str_canonical_sorted():
    dnf = [[Condition("B", "=", "2"), Condition("A", "=", "1")]]
    assert _global_guard_str(dnf) == "A = 1 AND B = 2"


def test_global_guard_str_true_when_empty():
    assert _global_guard_str([[]]) == "TRUE"


import itertools

import pytest

from gfsm.compose import compose_global
from gfsm.model import GfsmError


def test_two_fsm_product_hand_computed():
    # A: 10 --(P=1)--> 20 ;  B: 30 --(Q=1)--> 40
    a = _fb("A", ["10", "20"], [("10", "20", "P = 1")], case="SA")
    b = _fb("B", ["30", "40"], [("30", "40", "Q = 1")], case="SB")
    m = Metadata("s", "t", 0, 0)
    g = compose_global(
        {"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)}, max_states=100
    )
    assert g.initial == "p1:10|p2:30"
    ids = set(g.states.keys())
    assert "p1:10|p2:30" in ids
    assert "p1:20|p2:40" in ids
    # Semantics B (full product + optional stutter): from the initial state
    # each component may move or stutter; the all-stutter step is dropped.
    # So 3 successors: joint move, A-only (B stutters), B-only (A stutters).
    out = sorted(
        (t["to"], t["guard"]) for t in g.transitions
        if t["from"] == "p1:10|p2:30"
    )
    assert out == [
        ("p1:10|p2:40", "Q = 1"),
        ("p1:20|p2:30", "P = 1"),
        ("p1:20|p2:40", "P = 1 AND Q = 1"),
    ]
    joint = [
        t for t in g.transitions
        if t["from"] == "p1:10|p2:30" and t["to"] == "p1:20|p2:40"
    ]
    assert len(joint) == 1
    assert joint[0]["components"] == {
        "p1:A": "10_to_20", "p2:B": "30_to_40"
    }


def test_stutter_when_one_component_dead():
    # A moves; B has no outgoing from its initial -> B stutters.
    a = _fb("A", ["10", "20"], [("10", "20", "P = 1")], case="SA")
    b = _fb("B", ["30"], [], case="SB")
    m = Metadata("s", "t", 0, 0)
    g = compose_global(
        {"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)}, max_states=100
    )
    out = [t for t in g.transitions if t["from"] == "p1:10|p2:30"]
    assert len(out) == 1
    assert out[0]["to"] == "p1:20|p2:30"
    assert out[0]["components"]["p2:B"] is None  # stuttered
    assert out[0]["guard"] == "P = 1"


def test_all_stutter_step_dropped():
    # Both components have no viable outgoing -> no global transition.
    a = _fb("A", ["10"], [], case="SA")
    b = _fb("B", ["30"], [], case="SB")
    m = Metadata("s", "t", 0, 0)
    g = compose_global(
        {"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)}, max_states=100
    )
    assert g.transitions == []
    assert list(g.states.keys()) == ["p1:10|p2:30"]


def test_unsat_combination_pruned():
    # A: 10->20 guard X=high ; B: 30->40 guard X=low.
    # Joint move conjoins to X=high AND X=low -> unsat (pruned). The
    # surviving non-all-stutter combos are the two single-mover steps.
    a = _fb("A", ["10", "20"], [("10", "20", "X = high")], case="SA")
    b = _fb("B", ["30", "40"], [("30", "40", "X = low")], case="SB")
    m = Metadata("s", "t", 0, 0)
    g = compose_global(
        {"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)}, max_states=100
    )
    out = sorted(
        (t["to"], t["guard"]) for t in g.transitions
        if t["from"] == "p1:10|p2:30"
    )
    assert out == [
        ("p1:10|p2:40", "X = low"),
        ("p1:20|p2:30", "X = high"),
    ]


def test_determinism_repeated_runs_identical():
    a = _fb("A", ["10", "20"], [("10", "20", "P = 1")], case="SA")
    b = _fb("B", ["30", "40"], [("30", "40", "Q = 1")], case="SB")
    m = Metadata("s", "t", 0, 0)
    g1 = compose_global({"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)},
                        max_states=100)
    g2 = compose_global({"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)},
                        max_states=100)
    assert list(g1.states.keys()) == list(g2.states.keys())
    assert g1.transitions == g2.transitions


def test_max_states_overflow_raises():
    # Two independent 3-cycles -> full product 9 reachable; cap 4 -> raise.
    a = _fb("A", ["10", "20", "30"],
            [("10", "20", "No Check"), ("20", "30", "No Check"),
             ("30", "10", "No Check")], case="SA")
    b = _fb("B", ["40", "50", "60"],
            [("40", "50", "No Check"), ("50", "60", "No Check"),
             ("60", "40", "No Check")], case="SB")
    m = Metadata("s", "t", 0, 0)
    with pytest.raises(GfsmError, match="max-states"):
        compose_global({"p1": LocalFSM([a], m), "p2": LocalFSM([b], m)},
                       max_states=4)
