import json
from pathlib import Path

import pytest

from gfsm.driver import analyze_topology

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "data" / "generated"
TOPOLOGY = "ctown"
_MANIFEST = (
    GEN / TOPOLOGY / "analysis" / f"{TOPOLOGY}_analysis_manifest.json"
)


@pytest.mark.skipif(not _MANIFEST.exists(), reason="Stage 2 data missing")
def test_gfsm_nontrivial_and_deterministic(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    m = analyze_topology(generated_dir=GEN, topology=TOPOLOGY, out_dir=a)
    analyze_topology(generated_dir=GEN, topology=TOPOLOGY, out_dir=b)

    g = json.loads((a / f"{TOPOLOGY}.gfsm.json").read_text())
    assert len(g["states"]) >= 1
    assert g["initial"] in g["states"]
    expected_components = sum(
        p.get("counts", {}).get("function_blocks", 0) for p in m["plcs"]
    )
    assert expected_components >= 1
    assert len(g["initial"].split("|")) == expected_components
    assert m["gfsm"]["states"] == len(g["states"])

    for name in [f"{TOPOLOGY}.gfsm.json", f"{TOPOLOGY}.gfsm.dot",
                 f"{TOPOLOGY}.gfsm.analysis.json"]:
        assert (a / name).read_text() == (b / name).read_text(), name


_GFSM_JSON = GEN / TOPOLOGY / "gfsm" / f"{TOPOLOGY}.gfsm.json"


@pytest.mark.skipif(
    not _GFSM_JSON.exists(), reason="ctown gfsm not regenerated")
def test_ctown_gfsm_is_fully_composed():
    """Locks in the Stage-4 fix: ctown's GFSM is the full per-actuator
    product (paper Def 1/2), not the pre-fix lead-actuator-per-PLC
    under-composition (which had 3 segments / 8 states)."""
    g = json.loads(_GFSM_JSON.read_text())
    sample = next(iter(g["states"]))
    assert sample.count("|") + 1 > 3, (
        f"ctown GFSM under-composed: {sample!r} has too few segments")
    assert len(g["states"]) > 8, (
        f"ctown GFSM has only {len(g['states'])} states — expected the "
        f"full per-actuator product (much greater than 8)")
