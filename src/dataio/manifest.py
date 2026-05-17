"""Dataset provenance manifest (committed alongside normalized data)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .model import DataIoError

SCHEMA = "dataio/v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def build_dataset_manifest(
    *,
    topology: str,
    source_name: str,
    source_note: str,
    fmt: str,
    root: Path,
    calibration_files: list[str],
    evaluation_files: list[str],
    column_map: dict[str, str],
    attack_windows: list[tuple[str, str, str]],
) -> dict[str, Any]:
    root = Path(root)
    files = calibration_files + evaluation_files
    return {
        "schema": SCHEMA,
        "topology": topology,
        "source": {"name": source_name, "note": source_note, "format": fmt},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "calibration": list(calibration_files),
            "evaluation": list(evaluation_files),
        },
        "sha256": {rel: sha256_file(root / rel) for rel in files},
        "column_map": dict(column_map),
        "attack_windows": [
            {"id": a, "start": s, "end": e} for (a, s, e) in attack_windows
        ],
    }


def load_dataset_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise DataIoError(f"dataset manifest not found: {path}")
    return yaml.safe_load(path.read_text())
