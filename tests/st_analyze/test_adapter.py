from xml.etree import ElementTree as ET

from st_analyze.adapter import analyze_source

TINY_ST = """\
PROGRAM PLC1
VAR
    P1_State : INT := 0;
END_VAR
CASE P1_State OF
    0:
        IF T1 < 5 THEN
            P1_State := 1;
        END_IF;
END_CASE;
END_PROGRAM
"""

EMPTY_ST = "PROGRAM PLC2\n(* no actuators *)\nEND_PROGRAM\n"


def test_analyze_source_returns_well_formed_xml():
    r = analyze_source(TINY_ST)
    ET.fromstring(r.ast_xml)  # raises if malformed
    assert r.ast_xml.strip()


def test_analyze_source_produces_pdg_and_invariant_containers():
    r = analyze_source(TINY_ST)
    assert isinstance(r.invariants, list)
    assert isinstance(r.pdg_structured, dict)
    assert "digraph" in r.pdg_dot.lower() or r.pdg_dot == ""
    assert r.ok is True
    assert r.programs  # PDG state keys present (e.g. ["0"])


def test_analyze_empty_program_is_ok_not_crash():
    r = analyze_source(EMPTY_ST)
    assert r.ok is True
    assert isinstance(r.invariants, list)


def test_invariants_are_json_serializable_dicts():
    import json

    r = analyze_source(TINY_ST)
    json.dumps(r.invariants)  # raises if not serializable
    for inv in r.invariants:
        assert "type" in inv and "id" in inv


def test_malformed_source_sets_not_ok_without_raising():
    # Garbage that the analyzer grammar cannot parse must not escape
    # as an unhandled exception; analyze_source must return ok=False.
    r = analyze_source("@@@ this is definitely not structured text @@@")
    assert r.ok is False
    assert r.errors
    assert r.ast_xml == ""
    assert r.invariants == []
    assert r.pdg_structured == {}
