"""Composite-state encoding — single source of truth for mining + runtime.

The encoded format MUST be byte-identical to gfsm.compose._encode so that a
label produced here is a valid key in the GFSM JSON's `states` map.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .model import InvariantsError


def encode(components: list[tuple[str, str]], local_ids: tuple[str, ...]) -> str:
    """Encode (plc, case_var) components + their state IDs.

    Byte-identical to gfsm.compose._encode (the single source of truth):
    "|".join(f"{plc}.{case_var}:{sid}").
    """
    if len(components) != len(local_ids):
        raise InvariantsError(
            f"component/local_ids length mismatch: "
            f"{len(components)} vs {len(local_ids)}"
        )
    return "|".join(
        f"{plc}.{cv}:{sid}"
        for (plc, cv), sid in zip(components, local_ids)
    )


def load_gfsm_components(gfsm_dict: dict[str, Any]) -> list[tuple[str, str]]:
    """Recover the ordered (plc, case_var) components from a GFSM JSON.

    Each `|` segment is `<plc>.<case_var>:<sid>`. Split on the LAST ':'
    to peel `sid` (sid is digits, never contains ':' or '.'), then on the
    FIRST '.' to separate plc from case_var (plc never contains '.';
    case_var may in principle, so first-split is correct).
    """
    states = gfsm_dict.get("states") or {}
    if not states:
        raise InvariantsError("gfsm json has no 'states'")
    sample_key = next(iter(states))
    components: list[tuple[str, str]] = []
    for part in sample_key.split("|"):
        if ":" not in part or "." not in part:
            raise InvariantsError(
                f"malformed gfsm state key segment {part!r} in "
                f"{sample_key!r} (expected <plc>.<case_var>:<sid>)"
            )
        left, _sid = part.rsplit(":", 1)
        plc, case_var = left.split(".", 1)
        components.append((plc, case_var))
    return components


def resolve_fb_to_col(
    components: list[tuple[str, str]],
    dataset_column_map: dict[str, str],
) -> dict[tuple[str, str], str]:
    """Map each (plc, case_var) component to its dataset CSV column.

    The actuator is derived directly from the CASE selector (st_gen spec
    §8.1: state vars are `<ACT>_State`), so resolution is exact per
    actuator — no "lead actuator per PLC" and no gfsm manifest needed.
    Column via the existing fallback chain: UPPER → S_+UPPER → lower().
    """
    col_map = {
        k.upper(): v for k, v in (dataset_column_map or {}).items()
    }
    out: dict[tuple[str, str], str] = {}
    for comp in components:
        plc, case_var = comp
        act = case_var.removesuffix("_State")
        au = act.upper()
        csv_col = (
            col_map.get(au)
            or col_map.get("S_" + au)
            or (au.lower() if au else "")
        )
        if not csv_col:
            raise InvariantsError(
                f"cannot resolve dataset column for gfsm component "
                f"(plc={plc}, case_var={case_var!r}, "
                f"actuator={act!r}); check dataset column_map"
            )
        out[comp] = csv_col
    if len(out) != len(components):
        raise InvariantsError(
            f"resolved {len(out)} columns for {len(components)} gfsm "
            f"components (duplicate component tuples?)"
        )
    return out


def label_frame(
    df: pd.DataFrame,
    components: list[tuple[str, str]],
    fb_to_col: dict[tuple[str, str], str],
) -> pd.Series:
    """Per row: encode the composite state from row values via fb_to_col."""
    missing = [c for c in components if fb_to_col.get(c) not in df.columns]
    if missing:
        raise InvariantsError(
            f"missing column(s) for components {missing} in dataframe "
            f"(columns={list(df.columns)[:8]})"
        )
    cols = [fb_to_col[c] for c in components]
    selected = df[cols]
    import numpy as np
    if not np.isfinite(selected.to_numpy(dtype="float64")).all():
        raise InvariantsError(
            f"non-finite (NaN/inf) value in state columns {cols}; "
            f"cannot derive composite state"
        )
    sub = selected.astype(int).astype(str)
    return sub.apply(
        lambda row: "|".join(
            f"{plc}.{cv}:{sid}"
            for (plc, cv), sid in zip(components, row)
        ),
        axis=1,
    )


def resolve_fb_to_col_from_paths(
    gfsm_dir: Path,
    topology: str,
    data_root: Path,
) -> tuple[dict[tuple[str, str], str], list[tuple[str, str]], dict[str, Any]]:
    """Read the gfsm json, gfsm manifest, and dataset column_map from disk
    and resolve fb_to_col. Returns (fb_to_col, components, gfsm_json).

    Single shared file-resolution path for cli.py, monitor/driver.py, and
    the golden tests — raises InvariantsError on any missing input.
    """
    gfsm_path = Path(gfsm_dir) / f"{topology}.gfsm.json"
    if not gfsm_path.exists():
        raise InvariantsError(f"gfsm json not found: {gfsm_path}")
    gman_path = Path(gfsm_dir) / f"{topology}_gfsm_manifest.json"
    if not gman_path.exists():
        raise InvariantsError(f"gfsm manifest not found: {gman_path}")
    ds_man = Path(data_root) / topology / "dataset" / "dataset_manifest.yaml"
    if not ds_man.exists():
        raise InvariantsError(f"dataset manifest not found: {ds_man}")
    gfsm_json = json.loads(gfsm_path.read_text())
    components = load_gfsm_components(gfsm_json)
    gfsm_manifest = json.loads(gman_path.read_text())
    # gfsm_manifest is loaded above for existence/provenance validation
    # only; per-actuator resolution derives the actuator from case_var.
    _ = gfsm_manifest
    col_map = (yaml.safe_load(ds_man.read_text()) or {}).get(
        "column_map") or {}
    fb_to_col = resolve_fb_to_col(components, col_map)
    return fb_to_col, components, gfsm_json
