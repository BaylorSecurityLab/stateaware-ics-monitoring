import pytest

from st_gen.model import (
    Control,
    MultiStateActuatorError,
    Network,
    Plc,
    Pump,
    StGenError,
    Tank,
    UnsupportedControlError,
    UnsupportedRulesError,
    ValidationError,
    Valve,
)


def test_dataclasses_are_frozen():
    t = Tank(id="T1", min_level=0.0, max_level=4.0)
    with pytest.raises(Exception):
        t.id = "X"


def test_network_holds_lists():
    n = Network(
        tanks=[Tank(id="T1", min_level=0.0, max_level=4.0)],
        pumps=[Pump(id="P1", node1="A", node2="B")],
        valves=[Valve(id="V1", node1="C", node2="D", vtype="PRV", setting=40.0)],
        controls=[
            Control(
                link_id="P1",
                target_state="OPEN",
                sensor_node="T1",
                comparator="BELOW",
                threshold=2.4,
            )
        ],
    )
    assert n.tanks[0].id == "T1"
    assert n.controls[0].link_id == "P1"


def test_plc_dataclass():
    p = Plc(name="PLC1", sensors=["T1"], actuators=["P1"])
    assert p.name == "PLC1"
    assert p.sensors == ["T1"]
    assert p.actuators == ["P1"]


@pytest.mark.parametrize(
    "exc",
    [
        UnsupportedControlError,
        UnsupportedRulesError,
        MultiStateActuatorError,
        ValidationError,
    ],
)
def test_all_errors_subclass_stgenerror(exc):
    assert issubclass(exc, StGenError)
