"""Stage-3 STL manifest (provenance + per-scenario status)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SCHEMA = "stl/v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(*, topology: str, dataset_manifest_text: str,
                   n_formulas: int, scenarios: list[dict[str, Any]],
                   all_ok: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "topology": topology,
        "dataset_manifest_sha256": _sha(dataset_manifest_text),
        "n_formulas": n_formulas,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": scenarios,
        "all_ok": all_ok,
    }
