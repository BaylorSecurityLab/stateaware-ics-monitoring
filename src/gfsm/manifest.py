"""Stage-4 GFSM manifest: provenance + per-PLC status.

Mirrors src/st_analyze/manifest.py. The Rust port is pinned to upstream
commit 14950d5; recorded here as port provenance.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

SCHEMA = "gfsm/v1"
PORTED_FROM = "github.com/LaBackDoor/fsm-extractor"
PORTED_COMMIT = "14950d5c1c4e9c44695a266187e5e07fbd1620db"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    topology: str,
    source_manifest_name: str,
    source_manifest_text: str,
    plc_entries: list[dict[str, Any]],
    gfsm_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "topology": topology,
        "source_manifest": source_manifest_name,
        "source_manifest_sha256": sha256_text(source_manifest_text),
        "analyzer": {
            "package": "gfsm",
            "ported_from": PORTED_FROM,
            "commit": PORTED_COMMIT,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gfsm": gfsm_summary,
        "plcs": plc_entries,
    }
