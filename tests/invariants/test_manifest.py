from invariants.manifest import build_manifest, sha256_text


def test_sha256_stable_hex():
    assert sha256_text("hello") == \
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_build_manifest_shape():
    m = build_manifest(
        topology="anytown",
        gfsm_manifest_name="anytown_gfsm_manifest.json",
        gfsm_manifest_text="{}",
        dataset_manifest_name="dataset_manifest.yaml",
        dataset_manifest_text="files: {}",
        niaarm_cfg={"max_evals": 5000, "confidence_min": 0.7,
                    "support_min": 0.1, "min_observations": 50,
                    "seed": 42, "algorithm": "ParticleSwarmAlgorithm"},
        states_summary={"PLC1:0|PLC1:0": {"observations": 100, "rules": 3,
                                          "status": "ok"}},
        all_ok=True,
    )
    assert m["schema"] == "invariants/v1"
    assert m["topology"] == "anytown"
    assert m["gfsm_manifest"] == "anytown_gfsm_manifest.json"
    assert len(m["gfsm_manifest_sha256"]) == 64
    assert len(m["dataset_manifest_sha256"]) == 64
    assert m["niaarm"]["seed"] == 42
    assert m["all_ok"] is True
    assert m["states"]["PLC1:0|PLC1:0"]["rules"] == 3
    assert "generated_at" in m
