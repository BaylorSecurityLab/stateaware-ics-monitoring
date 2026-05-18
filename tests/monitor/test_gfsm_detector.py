import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monitor.gfsm_detector import GfsmAnomalyDetector


def _write_gfsm(tmp_path: Path, name: str = "synth"):
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / f"{name}.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0",
        "states": {"PLC1.S:0": ["0"], "PLC1.S:1": ["1"]},
        "transitions": [
            {"id": "t0", "from_state": "PLC1.S:0", "to_state": "PLC1.S:1",
             "condition": "T1 < 2.4", "raw_expression": ""},
            {"id": "t1", "from_state": "PLC1.S:1", "to_state": "PLC1.S:0",
             "condition": "T1 > 3.9", "raw_expression": ""},
        ],
        "metadata": {"source_file": "x", "extraction_date": "",
                     "total_states": 2, "total_transitions": 2},
        "max_states": 100,
    }))
    (gfsm_dir / f"{name}_gfsm_manifest.json").write_text(json.dumps({"x": 1}))
    return gfsm_dir


def test_clean_trace_no_flags(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    # states: 0(stutter)->0->1(legal t0)->0(legal t1): no flags
    frame = pd.DataFrame({"p1": [0, 0, 1, 0]})
    out = det.predict(frame)
    assert (out.flags == np.zeros(4, dtype=int)).all()


def test_unknown_state_flagged(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    # p1=2 -> "PLC1.S:2" not in states -> flag at row 2
    out = det.predict(pd.DataFrame({"p1": [0, 1, 2, 0]}))
    assert out.flags[2] == 1


def test_missing_column_raises_monitor_error(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    from monitor.model import MonitorError
    with pytest.raises(MonitorError):
        det.predict(pd.DataFrame({"other": [0, 1]}))


def test_missing_gfsm_json_raises_monitor_error(tmp_path: Path):
    from monitor.model import MonitorError
    det = GfsmAnomalyDetector(
        gfsm_dir=tmp_path, topology="absent",
        fb_to_col={("PLC1", "S"): "p1"},
    )
    with pytest.raises(MonitorError, match="gfsm json not found"):
        det.fit([])


def test_illegal_known_to_known_transition_flagged(tmp_path: Path):
    # Build a gfsm where the ONLY legal move is 0->1 (no 1->0). Then a
    # trace 0 -> 1 -> 0 must flag row 2 (the illegal 1->0).
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "oneway.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0",
        "states": {"PLC1.S:0": ["0"], "PLC1.S:1": ["1"]},
        "transitions": [
            {"id": "t0", "from_state": "PLC1.S:0", "to_state": "PLC1.S:1",
             "condition": "", "raw_expression": ""},
        ],
        "metadata": {"source_file": "x", "extraction_date": "",
                     "total_states": 2, "total_transitions": 1},
        "max_states": 100,
    }))
    (gfsm_dir / "oneway_gfsm_manifest.json").write_text(json.dumps({"x": 1}))
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="oneway",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    out = det.predict(pd.DataFrame({"p1": [0, 1, 0]}))
    # row0: known, no pred -> 0; row1: 0->1 legal -> 0; row2: 1->0 NOT in
    # allowed -> flagged.
    assert out.flags.tolist() == [0, 0, 1]


def test_row0_unknown_state_flagged(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    # p1=2 -> "PLC1.S:2" not a known state, AND it is row 0 -> flagged.
    out = det.predict(pd.DataFrame({"p1": [2, 0]}))
    assert out.flags[0] == 1


def test_unknown_then_recovery_is_conservatively_flagged(tmp_path: Path):
    # Documented INTENTIONAL semantic: an unknown composite state is itself
    # anomalous, and continuity THROUGH it cannot be validated against δ,
    # so the first known row after an unknown gap is conservatively flagged
    # (state-aware security errs toward flagging when conformance is
    # unprovable). Trace 0 -> 2(unknown) -> 1.
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "S"): "p1"},
    ).fit([])
    out = det.predict(pd.DataFrame({"p1": [0, 2, 1]}))
    # row0: 0 known, no pred -> 0
    # row1: "PLC1.S:2" unknown -> 1
    # row2: 1 known but prev="PLC1.S:2" (unknown) so ("PLC1.S:2","PLC1.S:1")
    #       not in allowed -> conservatively flagged 1
    assert out.flags.tolist() == [0, 1, 1]


def test_real_gfsm_from_to_keys_are_honored(tmp_path: Path):
    # Real global gfsm json uses "from"/"to" (NOT from_state/to_state).
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "rk.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0",
        "states": {"PLC1.S:0": ["0"], "PLC1.S:1": ["1"]},
        "transitions": [
            {"id": "t0", "from": "PLC1.S:0", "to": "PLC1.S:1",
             "condition": "", "raw_expression": ""},
        ],
        "metadata": {"source_file": "x", "extraction_date": "",
                     "total_states": 2, "total_transitions": 1},
        "max_states": 100,
    }))
    (gfsm_dir / "rk_gfsm_manifest.json").write_text(json.dumps({"x": 1}))
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="rk",
        fb_to_col={("PLC1", "S"): "p1"}).fit([])
    # 0->1 legal (via real "from"/"to"), 1->0 NOT a transition -> flag row2
    out = det.predict(pd.DataFrame({"p1": [0, 1, 0]}))
    assert out.flags.tolist() == [0, 0, 1]


def test_transition_missing_keys_raises_monitor_error(tmp_path: Path):
    from monitor.model import MonitorError
    gfsm_dir = tmp_path / "gfsm"
    gfsm_dir.mkdir()
    (gfsm_dir / "bad.gfsm.json").write_text(json.dumps({
        "initial": "PLC1.S:0", "states": {"PLC1.S:0": ["0"]},
        "transitions": [{"id": "t0", "condition": ""}],  # no from/to
        "metadata": {"source_file": "x", "extraction_date": "",
                     "total_states": 1, "total_transitions": 1},
        "max_states": 100,
    }))
    (gfsm_dir / "bad_gfsm_manifest.json").write_text(json.dumps({"x": 1}))
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="bad",
        fb_to_col={("PLC1", "S"): "p1"})
    with pytest.raises(MonitorError, match="missing from/to keys"):
        det.fit([])
