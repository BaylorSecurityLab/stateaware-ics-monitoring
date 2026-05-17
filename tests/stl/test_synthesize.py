from stl.profiles import CTOWN
from stl.synthesize import synthesize


def test_synthesize_emits_expected_families():
    params = {
        "mb": {}, "mb_window": {},
        "tank": {"l_t1": {"h_min": 0.1, "h_max": 6.4, "slew_max": 0.3}},
        "pump": {1: {"mode": "varying", "f_on_min": 1.0, "f_on_max": 9.0,
                     "f_off_max": 0.5}},
        "valve": {}, "head": {}, "pressure": {}, "pslew": {}, "symmetry": {},
    }
    specs = synthesize(CTOWN, params)
    assert "RANGE_l_t1" in specs
    assert "SLEW_l_t1" in specs
    assert "PHYS_l_t1" in specs
    assert any(k.startswith("PUMP_ON_1") for k in specs)
    assert any(k.startswith("CTRL_HI_") for k in specs)
    assert all(isinstance(v, str) and v for v in specs.values())
