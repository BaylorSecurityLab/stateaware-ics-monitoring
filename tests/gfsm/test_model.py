import pytest

from gfsm.model import (
    FunctionBlock,
    GfsmError,
    GlobalFSM,
    LocalFSM,
    Metadata,
    State,
    Transition,
)


def test_state_new_defaults():
    s = State.new("10")
    assert s.id == "10"
    assert s.name is None
    assert s.transitions_out == []
    assert s.transitions_in == []


def test_transition_new_id_format():
    t = Transition.new("10", "20", "A = 1")
    assert t.id == "10_to_20"
    assert t.from_state == "10"
    assert t.to_state == "20"
    assert t.condition == "A = 1"
    assert t.raw_expression == "A = 1"


def test_add_state_then_transition_updates_refs():
    fb = FunctionBlock.new("FB", "state")
    fb.add_state(State.new("10"))
    fb.add_state(State.new("20"))
    fb.add_transition(Transition.new("10", "20", "c"))
    assert fb.states["10"].transitions_out == ["10_to_20"]
    assert fb.states["20"].transitions_in == ["10_to_20"]
    assert len(fb.transitions) == 1
    assert fb.state_count() == 2
    assert fb.transition_count() == 1


def test_add_transition_missing_endpoint_is_silent():
    fb = FunctionBlock.new("FB", "state")
    fb.add_state(State.new("10"))
    fb.add_transition(Transition.new("10", "99", "c"))
    assert fb.states["10"].transitions_out == ["10_to_99"]
    assert "99" not in fb.states
    assert len(fb.transitions) == 1


def test_states_preserve_insertion_order():
    fb = FunctionBlock.new("FB", "s")
    for sid in ("30", "10", "20"):
        fb.add_state(State.new(sid))
    assert list(fb.states.keys()) == ["30", "10", "20"]


def test_metadata_fields():
    m = Metadata(
        source_file="x.xml",
        extraction_date="2026-05-17T00:00:00+00:00",
        total_states=2,
        total_transitions=1,
    )
    assert m.total_states == 2


def test_localfsm_and_globalfsm_construct():
    fb = FunctionBlock.new("FB", "s")
    m = Metadata("x", "t", 0, 0)
    lf = LocalFSM(function_blocks=[fb], metadata=m)
    assert lf.function_blocks[0].name == "FB"
    g = GlobalFSM(
        states={}, transitions=[], initial="", metadata=m, max_states=100
    )
    assert g.initial == ""


def test_gfsmerror_is_exception():
    with pytest.raises(GfsmError):
        raise GfsmError("boom")
