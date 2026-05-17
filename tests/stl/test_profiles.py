import pytest

from stl.profiles import get_profile, PROFILES
from stl.model import StlError


def test_three_profiles_present():
    assert set(PROFILES) == {"anytown", "ctown", "ltown"}


def test_ctown_profile_shape():
    p = get_profile("ctown")
    assert p.pump_status_fmt.format(pid=2) == "s_pu2"
    assert p.pump_flow_fmt.format(pid=2) == "f_pu2"
    assert "l_t1" in p.tanks
    assert p.hysteresis == 2


def test_unknown_profile_raises():
    with pytest.raises(StlError):
        get_profile("nope")
