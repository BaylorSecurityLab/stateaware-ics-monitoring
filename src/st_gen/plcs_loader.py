"""Loader for DHALSIM-style plcs.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from .model import Plc, ValidationError


def load_plcs(path: str | Path) -> list[Plc]:
    """Parse a DHALSIM-style plcs.yaml into a list of Plc."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValidationError(
            f"plcs.yaml must be a list at top level, got {type(raw).__name__}"
        )
    plcs: list[Plc] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValidationError(f"plcs.yaml entry {i} is not a mapping")
        if "name" not in entry or not isinstance(entry["name"], str):
            raise ValidationError(f"plcs.yaml entry {i} missing string 'name'")
        name = entry["name"]
        if name in seen:
            raise ValidationError(f"duplicate PLC name {name!r} at entry {i}")
        seen.add(name)
        sensors = entry.get("sensors") or []
        actuators = entry.get("actuators") or []
        if not isinstance(sensors, list) or not all(isinstance(s, str) for s in sensors):
            raise ValidationError(f"PLC {name!r} 'sensors' must be a list of strings")
        if not isinstance(actuators, list) or not all(isinstance(a, str) for a in actuators):
            raise ValidationError(f"PLC {name!r} 'actuators' must be a list of strings")
        plcs.append(Plc(name=name, sensors=list(sensors), actuators=list(actuators)))
    return plcs
