import pandas as pd
import pytest

from invariants.model import InvariantsError
from invariants.state_label import encode, label_frame, load_gfsm_components

SAMPLE_GFSM = {
    "initial": "PLC1:0|PLC1:0",
    "states": {"PLC1:0|PLC1:0": ["0", "0"], "PLC1:0|PLC1:1": ["0", "1"],
               "PLC1:1|PLC1:0": ["1", "0"], "PLC1:1|PLC1:1": ["1", "1"]},
    "transitions": [],
    "metadata": {"source_file": "anytown_plc1.st", "extraction_date": "",
                 "total_states": 4, "total_transitions": 0},
    "max_states": 100000,
}
SAMPLE_COMPONENTS = [("PLC1", "P78"), ("PLC1", "P79")]


def test_encode_matches_gfsm_format():
    assert encode(SAMPLE_COMPONENTS, ("0", "1")) == "PLC1:0|PLC1:1"
    assert encode(SAMPLE_COMPONENTS, ("1", "1")) == "PLC1:1|PLC1:1"


def test_load_components_recovers_plc_in_order():
    comps = load_gfsm_components(SAMPLE_GFSM)
    assert [c[0] for c in comps] == ["PLC1", "PLC1"]
    assert len(comps) == 2


def test_label_frame_uses_fb_to_col_map():
    df = pd.DataFrame({"p78": [0, 0, 1, 1], "p79": [0, 1, 0, 1]})
    fb_to_col = {("PLC1", "P78"): "p78", ("PLC1", "P79"): "p79"}
    labels = label_frame(df, SAMPLE_COMPONENTS, fb_to_col)
    assert labels.tolist() == ["PLC1:0|PLC1:0", "PLC1:0|PLC1:1",
                               "PLC1:1|PLC1:0", "PLC1:1|PLC1:1"]


def test_label_frame_raises_on_missing_column():
    df = pd.DataFrame({"p78": [0, 1]})  # p79 absent
    fb_to_col = {("PLC1", "P78"): "p78", ("PLC1", "P79"): "p79"}
    with pytest.raises(InvariantsError, match="missing column"):
        label_frame(df, SAMPLE_COMPONENTS, fb_to_col)
