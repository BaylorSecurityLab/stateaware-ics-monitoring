"""Gate: generated wadi.inp parses via st_gen and build() is idempotent."""

from pathlib import Path

import pytest

from scripts.gen_wadi_topology import build

REPO = Path(__file__).resolve().parents[2]
INP = REPO / "data" / "wadi" / "wadi.inp"


@pytest.mark.skipif(not INP.exists(), reason="wadi.inp not generated")
def test_wadi_inp_parses_via_st_gen():
    from st_gen import parse_inp

    net = parse_inp(INP)
    assert net is not None
    # must have parsed something meaningful
    assert len(net.pumps) + len(net.valves) > 0
    assert len(net.controls) > 0


@pytest.mark.skipif(not INP.exists(), reason="wadi.inp not generated")
def test_generator_idempotent():
    a = build()[0]
    b = build()[0]
    assert a == b
