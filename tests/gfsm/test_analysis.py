from gfsm.analysis import find_cycles
from gfsm.model import FunctionBlock, State, Transition


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
