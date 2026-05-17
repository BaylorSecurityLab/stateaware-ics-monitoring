import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from st_analyze.driver import analyze_topology

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "data" / "generated"
TOPOLOGY = "ltown"


@pytest.mark.skipif(
    not (GEN / TOPOLOGY / f"{TOPOLOGY}_manifest.json").exists(),
    reason="generated data missing",
)
def test_every_plc_analyzed_and_artifacts_valid(tmp_path: Path):
    out = tmp_path / "analysis"
    manifest = analyze_topology(
        generated_dir=GEN, topology=TOPOLOGY, out_dir=out
    )

    src = json.loads(
        (GEN / TOPOLOGY / f"{TOPOLOGY}_manifest.json").read_text()
    )
    assert len(manifest["plcs"]) == len(src["plcs"])

    for entry in manifest["plcs"]:
        assert entry["status"] == "ok", f"{entry['name']}: {entry.get('errors')}"
        stem = Path(entry["st_file"]).stem
        ET.fromstring((out / f"{stem}.ast.xml").read_text())  # well-formed
        invs = json.loads((out / f"{stem}.invariants.json").read_text())
        assert isinstance(invs, list)
        # PLCs with FSMs must yield a non-empty PDG (paper Definition 1).
        if entry["st_gen_fsms"]:
            assert entry["counts"]["pdg_nodes"] >= 1


@pytest.mark.skipif(
    not (GEN / TOPOLOGY / f"{TOPOLOGY}_manifest.json").exists(),
    reason="generated data missing",
)
def test_analysis_is_deterministic(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    analyze_topology(generated_dir=GEN, topology=TOPOLOGY, out_dir=a)
    analyze_topology(generated_dir=GEN, topology=TOPOLOGY, out_dir=b)

    for name in sorted(p.name for p in a.iterdir()):
        if name.endswith("_analysis_manifest.json"):
            continue  # contains generated_at timestamp
        assert (a / name).read_text() == (b / name).read_text(), name
