"""Stage-2 analysis manifest: provenance for downstream stages."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SCHEMA = "st_analyze/v1"
ANALYZER_COMMIT = "3431cad8850d50f553c87457216dc87c6cb9b310"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    topology: str,
    source_manifest_name: str,
    source_manifest_text: str,
    plc_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "topology": topology,
        "source_manifest": source_manifest_name,
        "source_manifest_sha256": sha256_text(source_manifest_text),
        "analyzer": {
            "package": "iec_st_compiler",
            "vendored_from": "github.com/LaBackDoor/iec_st_compiler",
            "commit": ANALYZER_COMMIT,
        },
        "comment_pattern": "default",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plcs": plc_entries,
    }
