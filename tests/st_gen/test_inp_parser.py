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


def test_unsupported_control_at_time(tmp_path):
    from st_gen.model import UnsupportedControlError
    inp = tmp_path / "bad.inp"
    inp.write_text(
        "[CONTROLS]\nLINK PUMP1 OPEN AT TIME 5\n[END]\n",
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedControlError) as exc:
        parse_inp(inp)
    assert "LINK PUMP1 OPEN AT TIME 5" in str(exc.value)
    assert "line 2" in str(exc.value)


def test_unsupported_rules_raises(tmp_path):
    from st_gen.model import UnsupportedRulesError
    inp = tmp_path / "rules.inp"
    inp.write_text(
        "[RULES]\nRULE bad\nIF NODE T1 ABOVE 5\nTHEN LINK P1 STATUS = CLOSED\n[END]\n",
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedRulesError) as exc:
        parse_inp(inp)
    assert "[RULES]" in str(exc.value)


def test_empty_rules_section_ok(tmp_path):
    inp = tmp_path / "ok.inp"
    inp.write_text(
        "[CONTROLS]\nLINK PUMP1 OPEN IF NODE T1 BELOW 2.0\n[RULES]\n\n; comment\n[END]\n",
        encoding="utf-8",
    )
    net = parse_inp(inp)
    assert len(net.controls) == 1
