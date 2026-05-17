from gfsm.compose import (
    Component,
    _component_choices,
    _component_initial,
    _encode,
    _ordered_components,
)
from gfsm.model import FunctionBlock, LocalFSM, Metadata, State, Transition


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
