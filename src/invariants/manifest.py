"""Stage-invariants provenance manifest."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SCHEMA = "invariants/v1"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    topology: str,
    gfsm_manifest_name: str,
    gfsm_manifest_text: str,
    dataset_manifest_name: str,
    dataset_manifest_text: str,
    niaarm_cfg: dict[str, Any],
    states_summary: dict[str, dict[str, Any]],
    all_ok: bool,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "topology": topology,
        "gfsm_manifest": gfsm_manifest_name,
        "gfsm_manifest_sha256": sha256_text(gfsm_manifest_text),
        "dataset_manifest": dataset_manifest_name,
        "dataset_manifest_sha256": sha256_text(dataset_manifest_text),
        "niaarm": niaarm_cfg,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "states": states_summary,
        "all_ok": all_ok,
    }
