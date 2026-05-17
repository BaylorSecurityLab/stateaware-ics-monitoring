import json
from pathlib import Path

import pytest

from st_gen.model import (
    Control,
    MultiStateActuatorError,
    Network,
    Plc,
    Pump,
    Tank,
    Valve,
)
from st_gen.st_emitter import emit


def _net_minitown_like() -> Network:
    """One tank, one pump, two controls — minitown PUMP1/TANK pattern."""
    return Network(
        tanks=[Tank(id="TANK", min_level=0.0, max_level=6.5)],
        pumps=[Pump(id="PUMP1", node1="J1", node2="TANK")],
        valves=[],
        controls=[
            Control(
                link_id="PUMP1",
                target_state="OPEN",
                sensor_node="TANK",
                comparator="BELOW",
                threshold=4.0,
            ),
            Control(
                link_id="PUMP1",
                target_state="CLOSED",
                sensor_node="TANK",
                comparator="ABOVE",
                threshold=6.3,
            ),
        ],
    )


def test_emit_single_actuator(tmp_path):
    net = _net_minitown_like()
    plcs = [Plc(name="PLC1", sensors=["TANK"], actuators=["PUMP1"])]
    manifest = emit(net, plcs, out_dir=tmp_path, topology="mini")
    st_file = tmp_path / "mini_plc1.st"
    assert st_file.exists()
    text = st_file.read_text(encoding="utf-8")
    # Header
    assert "PROGRAM PLC1" in text
    assert "END_PROGRAM" in text
    # State variable + initial value
    assert "PUMP1_State : INT := 0;" in text
    # CASE block transitions
    assert "CASE PUMP1_State OF" in text
    assert "IF TANK < 4.0 THEN" in text
    assert "PUMP1_State := 1;" in text
    assert "IF TANK > 6.3 THEN" in text
    assert "PUMP1_State := 0;" in text
    # Output assignment
    assert "PUMP1 := (PUMP1_State = 1);" in text
    # Manifest
    assert manifest.topology == "mini"
    assert manifest.plcs[0]["actuators"] == ["PUMP1"]
