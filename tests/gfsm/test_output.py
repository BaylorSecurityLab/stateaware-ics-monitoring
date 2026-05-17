import json

from gfsm.model import FunctionBlock, LocalFSM, Metadata, State, Transition
from gfsm.output import fsm_to_dict, fsm_to_json


def _sample() -> LocalFSM:
    fb = FunctionBlock.new("FB", "S")
    fb.add_state(State.new("10"))
    fb.add_state(State.new("20"))
    fb.add_transition(Transition.new("10", "20", "A = 1"))
    m = Metadata("src.xml", "2026-05-17T00:00:00+00:00", 2, 1)
    return LocalFSM(function_blocks=[fb], metadata=m)


def test_fsm_to_dict_exact_structure():
    d = fsm_to_dict(_sample())
    assert list(d.keys()) == ["function_blocks", "metadata"]
    fb = d["function_blocks"][0]
    assert list(fb.keys()) == [
        "name", "case_variable", "states", "transitions"
    ]
    assert fb["states"]["10"] == {
        "id": "10", "name": None,
        "transitions_out": ["10_to_20"], "transitions_in": [],
    }
    assert fb["transitions"][0] == {
        "id": "10_to_20", "from_state": "10", "to_state": "20",
        "condition": "A = 1", "raw_expression": "A = 1",
    }
    assert d["metadata"]["source_file"] == "src.xml"


def test_fsm_to_json_is_2space_unsorted():
    js = fsm_to_json(_sample())
    assert js.startswith('{\n  "function_blocks"')
    # round-trips and preserves state insertion order
    back = json.loads(js)
    assert list(back["function_blocks"][0]["states"].keys()) == ["10", "20"]
