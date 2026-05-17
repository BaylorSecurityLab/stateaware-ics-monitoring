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


def test_emit_multi_actuator_and_cross_plc_sensor(tmp_path):
    net = Network(
        tanks=[Tank(id="T1", min_level=0.0, max_level=6.5)],
        pumps=[
            Pump(id="PU1", node1="J1", node2="T1"),
            Pump(id="PU2", node1="J1", node2="T1"),
        ],
        valves=[Valve(id="V2", node1="J2", node2="T2", vtype="TCV", setting=0.0)],
        controls=[
            Control("PU1", "OPEN", "T1", "BELOW", 4.0),
            Control("PU1", "CLOSED", "T1", "ABOVE", 6.3),
            Control("PU2", "OPEN", "T1", "BELOW", 1.0),
            Control("PU2", "CLOSED", "T1", "ABOVE", 4.5),
            Control("V2", "OPEN", "T2", "BELOW", 0.5),
            Control("V2", "CLOSED", "T2", "ABOVE", 5.5),
        ],
    )
    plcs = [
        Plc(name="PLC1", sensors=[], actuators=["PU1", "PU2"]),
        Plc(name="PLC2", sensors=["T1"], actuators=[]),
        Plc(name="PLC3", sensors=["T2"], actuators=["V2"]),
    ]
    emit(net, plcs, out_dir=tmp_path, topology="ct")

    p1 = (tmp_path / "ct_plc1.st").read_text(encoding="utf-8")
    # PLC1 references T1, which is owned by PLC2
    assert "T1 : REAL;" in p1
    assert "(* sourced from PLC2 *)" in p1
    # Both CASE blocks present
    assert "CASE PU1_State OF" in p1
    assert "CASE PU2_State OF" in p1
    # T1 deduplicated (one VAR_INPUT line, not two)
    assert p1.count("T1 : REAL;") == 1

    p3 = (tmp_path / "ct_plc3.st").read_text(encoding="utf-8")
    assert "T2 : REAL;" in p3
    assert "(* owned by this PLC *)" in p3


def test_emit_sensor_only_plc(tmp_path):
    net = Network(tanks=[], pumps=[], valves=[], controls=[])
    plcs = [Plc(name="PLC9", sensors=["T7"], actuators=[])]
    emit(net, plcs, out_dir=tmp_path, topology="ct")
    text = (tmp_path / "ct_plc9.st").read_text(encoding="utf-8")
    assert "PROGRAM PLC9" in text
    assert "No actuators with [CONTROLS] entries" in text
    assert "END_PROGRAM" in text


def test_emit_actuator_without_controls_is_empty_shell(tmp_path):
    # L-Town PRV pattern: actuator with static setting, no [CONTROLS].
    net = Network(
        tanks=[],
        pumps=[],
        valves=[Valve("PRV_1", "A", "B", "PRV", 40.0)],
        controls=[],
    )
    plcs = [Plc(name="PLC2", sensors=["p227"], actuators=["PRV_1"])]
    emit(net, plcs, out_dir=tmp_path, topology="lt")
    text = (tmp_path / "lt_plc2.st").read_text(encoding="utf-8")
    assert "PROGRAM PLC2" in text
    assert "No actuators with [CONTROLS] entries" in text
    assert "CASE" not in text   # no CASE blocks emitted
