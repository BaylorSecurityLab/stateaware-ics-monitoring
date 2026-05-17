from gfsm.compose import Component, _component_initial, _ordered_components
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
