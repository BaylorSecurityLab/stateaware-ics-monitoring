import numpy as np
import pandas as pd

from scripts.gen_wadi_topology import emit_inp, emit_plcs


def _fits():
    return [
        {"actuator": "1_p_001_status", "sensor": "1_lt_001_pv",
         "on_level": 0.2, "off_level": 0.8, "plc": "PLC1", "stage": 1},
        {"actuator": "2_mv_003_status", "sensor": "2_lt_002_pv",
         "on_level": 0.3, "off_level": 0.7, "plc": "PLC2", "stage": 2},
    ]


def test_emit_inp_has_required_sections_and_ids():
    txt = emit_inp(_fits())
    for sec in ("[TITLE]", "[JUNCTIONS]", "[TANKS]", "[PIPES]",
                "[PUMPS]", "[VALVES]", "[CONTROLS]", "[RULES]",
                "[COORDINATES]", "[OPTIONS]", "[END]"):
        assert sec in txt, sec
    assert "1_lt_001_pv" in txt and "1_p_001_status" in txt
    rules = txt.split("[RULES]")[1].split("[")[0].strip()
    assert rules == ""
    ctrl = txt.split("[CONTROLS]")[1].split("[")[0]
    assert "1_p_001_status" in ctrl and "1_lt_001_pv" in ctrl


def test_emit_plcs_groups_by_plc():
    y = emit_plcs(_fits())
    names = {p["name"] for p in y}
    assert names == {"PLC1", "PLC2"}
    p1 = next(p for p in y if p["name"] == "PLC1")
    assert "1_p_001_status" in p1["actuators"]
    assert "1_lt_001_pv" in p1["sensors"]
