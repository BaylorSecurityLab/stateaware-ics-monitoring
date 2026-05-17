"""Canonical snake_case naming for dataset columns / STL signal names."""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def canonical_name(raw: str) -> str:
    s = raw.strip().lower()
    s = _NON_ALNUM.sub("_", s)
    return s.strip("_")


def canonicalize_columns(columns: list[str]) -> dict[str, str]:
    return {c: canonical_name(c) for c in columns}
