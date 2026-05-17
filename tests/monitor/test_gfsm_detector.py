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
        "initial": "PLC1:0",
        "states": {"PLC1:0": ["0"], "PLC1:1": ["1"]},
        "transitions": [
            {"id": "t0", "from_state": "PLC1:0", "to_state": "PLC1:1",
             "condition": "T1 < 2.4", "raw_expression": ""},
            {"id": "t1", "from_state": "PLC1:1", "to_state": "PLC1:0",
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
        fb_to_col={("PLC1", "#0"): "p1"},
    ).fit([])
    # states: 0(stutter)->0->1(legal t0)->0(legal t1): no flags
    frame = pd.DataFrame({"p1": [0, 0, 1, 0]})
    out = det.predict(frame)
    assert (out.flags == np.zeros(4, dtype=int)).all()


def test_unknown_state_flagged(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "#0"): "p1"},
    ).fit([])
    # p1=2 -> "PLC1:2" not in states -> flag at row 2
    out = det.predict(pd.DataFrame({"p1": [0, 1, 2, 0]}))
    assert out.flags[2] == 1


def test_missing_column_raises_monitor_error(tmp_path: Path):
    gfsm_dir = _write_gfsm(tmp_path)
    det = GfsmAnomalyDetector(
        gfsm_dir=gfsm_dir, topology="synth",
        fb_to_col={("PLC1", "#0"): "p1"},
    ).fit([])
    from monitor.model import MonitorError
    with pytest.raises(MonitorError):
        det.predict(pd.DataFrame({"other": [0, 1]}))


def test_missing_gfsm_json_raises_monitor_error(tmp_path: Path):
    from monitor.model import MonitorError
    det = GfsmAnomalyDetector(
        gfsm_dir=tmp_path, topology="absent",
        fb_to_col={("PLC1", "#0"): "p1"},
    )
    with pytest.raises(MonitorError, match="gfsm json not found"):
        det.fit([])
