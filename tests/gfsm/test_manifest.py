from gfsm.manifest import SCHEMA, build_manifest, sha256_text


def test_sha256_matches_known():
    # hashlib.sha256(b"abc").hexdigest()
    assert sha256_text("abc").startswith("ba7816bf")


def test_manifest_shape_and_provenance():
    entries = [
        {"name": "PLC1", "ast_file": "anytown_plc1.ast.xml",
         "status": "ok", "errors": [],
         "artifacts": {"fsm_json": "anytown_plc1.fsm.json"},
         "counts": {"function_blocks": 1, "states": 2, "transitions": 1},
         "stage2_fsms": ["P78"]},
    ]
    m = build_manifest(
        topology="anytown",
        source_manifest_name="anytown_analysis_manifest.json",
        source_manifest_text="{}",
        plc_entries=entries,
        gfsm_summary={"states": 4, "transitions": 3, "initial": "x"},
    )
    assert m["schema"] == SCHEMA
    assert m["topology"] == "anytown"
    assert m["source_manifest"] == "anytown_analysis_manifest.json"
    assert m["source_manifest_sha256"] == sha256_text("{}")
    assert m["analyzer"]["package"] == "gfsm"
    assert "commit" in m["analyzer"]
    assert m["gfsm"] == {"states": 4, "transitions": 3, "initial": "x"}
    assert m["plcs"] == entries
    assert "generated_at" in m
