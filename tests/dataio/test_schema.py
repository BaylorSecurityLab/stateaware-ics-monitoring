from dataio.schema import canonical_name, canonicalize_columns


def test_canonical_name_lowercases_and_snakes():
    assert canonical_name("L_T1") == "l_t1"
    assert canonical_name("S_PU10") == "s_pu10"
    assert canonical_name("F_PU10") == "f_pu10"
    assert canonical_name("P_J280") == "p_j280"
    assert canonical_name("PUMP_1") == "pump_1"
    assert canonical_name(" DATETIME ") == "datetime"


def test_canonicalize_columns_returns_map_and_renamed():
    cols = ["L_T1", "S_PU1", "DATETIME"]
    mapping = canonicalize_columns(cols)
    assert mapping == {"L_T1": "l_t1", "S_PU1": "s_pu1", "DATETIME": "datetime"}
