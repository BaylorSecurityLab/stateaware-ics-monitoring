import json
from pathlib import Path

import pytest

from gfsm.driver import analyze_topology

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "data" / "generated"
TOPOLOGY = "anytown"
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
    # Guard against vacuous pass: a real product has >=1 state and the
    # initial state is well-formed (one component id per PLC FB).
    assert len(g["states"]) >= 1
    assert g["initial"] in g["states"]
    # Composed components = PLCs with status "ok" (skipped PLCs are
    # legitimately excluded; the initial tuple has one id per ok PLC).
    # Composed components = total function_blocks contributed across PLCs.
    # PLCs with 0 function_blocks (skipped or empty-FSM) contribute nothing.
    expected_components = sum(
        p.get("counts", {}).get("function_blocks", 0) for p in m["plcs"]
    )
    assert expected_components >= 1
    assert len(g["initial"].split("|")) == expected_components
    assert m["gfsm"]["states"] == len(g["states"])

    for name in [f"{TOPOLOGY}.gfsm.json", f"{TOPOLOGY}.gfsm.dot",
                 f"{TOPOLOGY}.gfsm.analysis.json"]:
        assert (a / name).read_text() == (b / name).read_text(), name
