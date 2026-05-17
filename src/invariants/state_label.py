"""Composite-state encoding — single source of truth for mining + runtime.

The encoded format MUST be byte-identical to gfsm.compose._encode so that a
label produced here is a valid key in the GFSM JSON's `states` map.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .model import InvariantsError


def encode(components: list[tuple[str, str]], local_ids: tuple[str, ...]) -> str:
    """Encode (plc, fb_name) components + their current state IDs."""
    if len(components) != len(local_ids):
        raise InvariantsError(
            f"component/local_ids length mismatch: "
            f"{len(components)} vs {len(local_ids)}"
        )
    return "|".join(
        f"{plc}:{sid}" for (plc, _fb), sid in zip(components, local_ids)
    )


def load_gfsm_components(gfsm_dict: dict[str, Any]) -> list[tuple[str, str]]:
    """Recover the (plc, fb_name) component ordering from a GFSM JSON dict.

    The GFSM JSON `states` keys carry only plc names per position (the
    fb_name is not recoverable from the key alone). The caller supplies the
    precise (plc, fb_name) tuples via the profile-derived fb_to_col map;
    this returns positional (plc, "#i") tuples in the correct ORDER so the
    caller can zip them against its own ordered fb list.
    """
    states = gfsm_dict.get("states") or {}
    if not states:
        raise InvariantsError("gfsm json has no 'states'")
    sample_key = next(iter(states))
    parts = sample_key.split("|")
    components: list[tuple[str, str]] = []
    for i, part in enumerate(parts):
        if ":" not in part:
            raise InvariantsError(
                f"malformed gfsm state key segment {part!r} in {sample_key!r}"
            )
        plc, _sid = part.split(":", 1)
        components.append((plc, f"#{i}"))
    return components


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
            f"{plc}:{sid}" for (plc, _fb), sid in zip(components, row)
        ),
        axis=1,
    )
