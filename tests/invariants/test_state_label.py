import pandas as pd
import pytest

from invariants.model import InvariantsError
from invariants.state_label import encode, label_frame, load_gfsm_components

SAMPLE_GFSM = {
    "initial": "PLC1.P78_State:0|PLC1.P79_State:0",
    "states": {
        "PLC1.P78_State:0|PLC1.P79_State:0": ["0", "0"],
        "PLC1.P78_State:0|PLC1.P79_State:1": ["0", "1"],
        "PLC1.P78_State:1|PLC1.P79_State:0": ["1", "0"],
        "PLC1.P78_State:1|PLC1.P79_State:1": ["1", "1"],
    },
    "transitions": [],
    "metadata": {"source_file": "anytown_plc1.st", "extraction_date": "",
                 "total_states": 4, "total_transitions": 0},
    "max_states": 100000,
}
SAMPLE_COMPONENTS = [("PLC1", "P78_State"), ("PLC1", "P79_State")]


def test_encode_matches_gfsm_format():
    assert encode(SAMPLE_COMPONENTS, ("0", "1")) == (
        "PLC1.P78_State:0|PLC1.P79_State:1")
    assert encode(SAMPLE_COMPONENTS, ("1", "1")) == (
        "PLC1.P78_State:1|PLC1.P79_State:1")


def test_encode_byte_identical_to_gfsm_encode():
    # Single source of truth (spec §4): invariants.encode MUST be
    # byte-identical to gfsm.compose._encode.
    from gfsm.compose import Component, _encode as g_encode
    from gfsm.model import FunctionBlock

    fb_a = FunctionBlock.new("V2_State", "V2_State")
    fb_b = FunctionBlock.new("PU4_State", "PU4_State")
    comps = [Component("PLC3", fb_a), Component("PLC3", fb_b)]
    gkey = g_encode(comps, ("0", "1"))

    components = [("PLC3", "V2_State"), ("PLC3", "PU4_State")]
    assert encode(components, ("0", "1")) == gkey
    assert encode(components, ("0", "1")) == "PLC3.V2_State:0|PLC3.PU4_State:1"


def test_load_components_recovers_plc_and_casevar_in_order():
    comps = load_gfsm_components(SAMPLE_GFSM)
    assert comps == [("PLC1", "P78_State"), ("PLC1", "P79_State")]


def test_load_components_recovers_multi_plc_casevar():
    gfsm = {"states": {"PLC3.V2_State:0|PLC3.PU4_State:1": ["0", "1"]}}
    assert load_gfsm_components(gfsm) == [
        ("PLC3", "V2_State"), ("PLC3", "PU4_State")]


def test_label_frame_uses_fb_to_col_map():
    df = pd.DataFrame({"p78": [0, 0, 1, 1], "p79": [0, 1, 0, 1]})
    fb_to_col = {("PLC1", "P78_State"): "p78", ("PLC1", "P79_State"): "p79"}
    labels = label_frame(df, SAMPLE_COMPONENTS, fb_to_col)
    assert labels.tolist() == [
        "PLC1.P78_State:0|PLC1.P79_State:0",
        "PLC1.P78_State:0|PLC1.P79_State:1",
        "PLC1.P78_State:1|PLC1.P79_State:0",
        "PLC1.P78_State:1|PLC1.P79_State:1",
    ]


def test_label_frame_emits_new_format():
    components = [("PLC3", "V2_State"), ("PLC3", "PU4_State")]
    fb_to_col = {components[0]: "s_v2", components[1]: "s_pu4"}
    df = pd.DataFrame({"s_v2": [0, 1], "s_pu4": [1, 0]})
    out = list(label_frame(df, components, fb_to_col))
    assert out == [
        "PLC3.V2_State:0|PLC3.PU4_State:1",
        "PLC3.V2_State:1|PLC3.PU4_State:0",
    ]


def test_label_frame_raises_on_missing_column():
    df = pd.DataFrame({"p78": [0, 1]})  # p79 absent
    fb_to_col = {("PLC1", "P78_State"): "p78", ("PLC1", "P79_State"): "p79"}
    with pytest.raises(InvariantsError, match="missing column"):
        label_frame(df, SAMPLE_COMPONENTS, fb_to_col)


def test_label_frame_raises_invariantserror_on_nan():
    df = pd.DataFrame({"p78": [0.0, float("nan")], "p79": [1.0, 1.0]})
    fb_to_col = {("PLC1", "P78_State"): "p78", ("PLC1", "P79_State"): "p79"}
    with pytest.raises(InvariantsError, match="non-finite|NaN"):
        label_frame(df, SAMPLE_COMPONENTS, fb_to_col)


def test_load_components_raises_on_malformed_key():
    bad = {"states": {"PLC1": ["0"]}}  # segment has no ':' or '.'
    with pytest.raises(InvariantsError, match="malformed"):
        load_gfsm_components(bad)


def test_load_components_raises_on_segment_without_dot():
    bad = {"states": {"PLC3_noseparators": ["0"]}}  # no '.' separator
    with pytest.raises(InvariantsError, match="malformed"):
        load_gfsm_components(bad)


def test_resolve_fb_to_col_per_actuator_column_map_chain():
    from invariants.state_label import resolve_fb_to_col
    comps = [("PLC3", "V2_State"), ("PLC1", "P78_State"),
             ("PLC2", "PUMP_1_State")]
    col_map = {"V2": "s_v2", "P78": "p78"}  # PUMP_1 only via .lower()
    out = resolve_fb_to_col(comps, col_map)
    assert out[("PLC3", "V2_State")] == "s_v2"
    assert out[("PLC1", "P78_State")] == "p78"
    assert out[("PLC2", "PUMP_1_State")] == "pump_1"  # lower() fallback


def test_resolve_fb_to_col_s_prefix_fallback():
    from invariants.state_label import resolve_fb_to_col
    out = resolve_fb_to_col([("PLC3", "PU4_State")], {"S_PU4": "s_pu4"})
    assert out[("PLC3", "PU4_State")] == "s_pu4"


def test_resolve_fb_to_col_unresolved_raises_naming_component():
    # Genuine unresolved condition: an empty actuator (case_var has no
    # name before "_State") yields nothing through the UPPER→S_+ACT→lower
    # chain, so it raises and the message names the component. (A non-empty
    # actuator always resolves via the lower() fallback by design — that
    # fallback is load-bearing for real lowercase dataset columns.)
    from invariants.model import InvariantsError
    from invariants.state_label import resolve_fb_to_col
    with pytest.raises(InvariantsError, match=r"PLC9.*_State"):
        resolve_fb_to_col([("PLC9", "_State")], {})
