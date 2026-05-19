from scripts.gen_wadi_topology import WADI_STRUCTURE, classify_columns


def test_structure_covers_documented_loops():
    assert WADI_STRUCTURE["1_p_001_status"]["sensor"] == "1_lt_001_pv"
    assert WADI_STRUCTURE["1_p_001_status"]["plc"] == "PLC1"
    assert WADI_STRUCTURE["2_mv_003_status"]["sensor"] == "2_lt_002_pv"
    for a, m in WADI_STRUCTURE.items():
        assert set(m) >= {"sensor", "plc", "stage"}
        assert m["stage"] in (1, 2, 3)


def test_classify_columns_splits_actuators_and_sensors():
    cols = ["Row", "Date", "1_LT_001_PV", "1_P_001_STATUS",
            "2_MCV_101_CO", "2_SV_101_STATUS", "1_AIT_001_PV"]
    act, sens = classify_columns(cols)
    assert "1_p_001_status" in act and "2_sv_101_status" in act
    assert "1_lt_001_pv" in sens and "1_ait_001_pv" in sens
    assert "2_mcv_101_co" not in act
