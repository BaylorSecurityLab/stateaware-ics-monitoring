from pathlib import Path

import pytest

from st_gen.inp_parser import parse_inp

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.inp"


def test_parse_tanks():
    net = parse_inp(FIXTURE)
    ids = [t.id for t in net.tanks]
    assert ids == ["T1", "T2"]
    t1 = next(t for t in net.tanks if t.id == "T1")
    assert t1.min_level == 0.0
    assert t1.max_level == 6.5
    t2 = next(t for t in net.tanks if t.id == "T2")
    assert t2.min_level == 0.5
    assert t2.max_level == 4.0


def test_parse_pumps():
    net = parse_inp(FIXTURE)
    assert len(net.pumps) == 1
    p = net.pumps[0]
    assert p.id == "PUMP1"
    assert p.node1 == "J1"
    assert p.node2 == "T1"


def test_parse_valves():
    net = parse_inp(FIXTURE)
    assert len(net.valves) == 1
    v = net.valves[0]
    assert v.id == "V1"
    assert v.vtype == "PRV"
    assert v.setting == 40.0


def test_parse_controls():
    net = parse_inp(FIXTURE)
    assert len(net.controls) == 2
    c0, c1 = net.controls
    assert c0.link_id == "PUMP1"
    assert c0.target_state == "OPEN"
    assert c0.sensor_node == "T1"
    assert c0.comparator == "BELOW"
    assert c0.threshold == 2.0
    assert c1.target_state == "CLOSED"
    assert c1.comparator == "ABOVE"
    assert c1.threshold == 5.5
