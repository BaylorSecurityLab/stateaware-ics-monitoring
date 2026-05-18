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


def test_label_frame_raises_invariantserror_on_nan():
    df = pd.DataFrame({"p78": [0.0, float("nan")], "p79": [1.0, 1.0]})
    fb_to_col = {("PLC1", "P78"): "p78", ("PLC1", "P79"): "p79"}
    with pytest.raises(InvariantsError, match="non-finite|NaN"):
        label_frame(df, SAMPLE_COMPONENTS, fb_to_col)


def test_load_components_raises_on_malformed_key():
    bad = {"states": {"PLC1": ["0"]}}  # segment has no ':'
    with pytest.raises(InvariantsError, match="malformed"):
        load_gfsm_components(bad)


def test_load_components_pins_positional_placeholders():
    sample = {"states": {"PLC1:0|PLC1:1": ["0", "1"]}}
    comps = load_gfsm_components(sample)
    assert [c[1] for c in comps] == ["#0", "#1"]


def test_resolve_fb_to_col_direct_and_s_prefix_and_lower():
    from invariants.state_label import resolve_fb_to_col
    comps = [("PLC1", "#0"), ("PLC3", "#1")]
    gman = {"plcs": [
        {"name": "PLC1", "counts": {"function_blocks": 1},
         "stage2_fsms": [{"actuator": "PU1"}]},
        {"name": "PLC3", "counts": {"function_blocks": 1},
         "stage2_fsms": [{"actuator": "P78"}]},
        {"name": "PLC9", "counts": {"function_blocks": 0},
         "stage2_fsms": []},
    ]}
    colmap = {"P78": "p78", "S_PU1": "s_pu1"}  # PLC1→PU1→S_PU1→s_pu1; PLC3→P78→p78
    m = resolve_fb_to_col(comps, gman, colmap)
    assert m == {("PLC1", "#0"): "s_pu1", ("PLC3", "#1"): "p78"}


def test_resolve_fb_to_col_lowercase_fallback():
    from invariants.state_label import resolve_fb_to_col
    comps = [("PLC1", "#0")]
    gman = {"plcs": [{"name": "PLC1", "counts": {"function_blocks": 1},
                      "stage2_fsms": [{"actuator": "PUMP_1"}]}]}
    m = resolve_fb_to_col(comps, gman, {})  # no column_map → PUMP_1→pump_1
    assert m == {("PLC1", "#0"): "pump_1"}


def test_resolve_fb_to_col_unresolvable_raises():
    import pytest
    from invariants.model import InvariantsError
    from invariants.state_label import resolve_fb_to_col
    comps = [("PLC1", "#0")]
    gman = {"plcs": [{"name": "PLC1", "counts": {"function_blocks": 0},
                      "stage2_fsms": []}]}  # no lead actuator → unresolvable
    with pytest.raises(InvariantsError, match="cannot resolve dataset column"):
        resolve_fb_to_col(comps, gman, {})
