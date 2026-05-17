import json

from st_analyze.manifest import build_manifest, sha256_text


def test_sha256_is_stable_hex():
    h = sha256_text("hello")
    assert h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_build_manifest_shape():
    src_manifest = {
        "topology": "anytown",
        "inp": "anytown.inp",
        "plcs_yaml": "anytown_plcs.yaml",
        "plcs": [{"name": "PLC1", "file": "anytown_plc1.st",
                  "fsms": [{"actuator": "P78", "states": 2, "transitions": 2}]}],
    }
    plc_entries = [{
        "name": "PLC1",
        "st_file": "anytown_plc1.st",
        "status": "ok",
        "artifacts": {"ast_xml": "analysis/anytown_plc1.ast.xml"},
        "counts": {"pdg_nodes": 7, "invariants_by_type": {"single": 2}},
        "st_gen_fsms": [{"actuator": "P78", "states": 2, "transitions": 2}],
    }]
    m = build_manifest(
        topology="anytown",
        source_manifest_name="anytown_manifest.json",
        source_manifest_text=json.dumps(src_manifest),
        plc_entries=plc_entries,
    )
    assert m["schema"] == "st_analyze/v1"
    assert m["topology"] == "anytown"
    assert m["source_manifest"] == "anytown_manifest.json"
    assert len(m["source_manifest_sha256"]) == 64
    assert m["analyzer"]["package"] == "iec_st_compiler"
    assert m["plcs"] == plc_entries
    assert "generated_at" in m
