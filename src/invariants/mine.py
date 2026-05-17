"""Thin wrapper over niaarm: mine numerical association rules per state slice.

The niaarm public API is pinned by tests/invariants/test_niaarm_api.py.
get_rules returns niaarm.mine.Result(rules, run_time); feature bounds are
coerced to native float so the Φ JSON is serializable.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .model import Atom, MinedRule


@dataclass(frozen=True)
class MinerConfig:
    max_evals: int = 5000
    confidence_min: float = 0.7
    support_min: float = 0.1
    seed: int = 42
    algorithm: str = "ParticleSwarmAlgorithm"


def _native(x: object) -> object:
    """Coerce numpy scalars / pandas values to JSON-native types."""
    if x is None:
        return None
    if isinstance(x, bool):
        return str(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        return str(x)


def _atom_from_feature(feat: object) -> Atom:
    """Convert a niaarm Feature to an Atom (JSON-native values only)."""
    name = getattr(feat, "name", "?")
    cats = getattr(feat, "categories", None)
    if cats:
        vals = [str(c) for c in cats]
        return Atom(col=name, op="in", val=vals)
    mn = _native(getattr(feat, "min_val", None))
    mx = _native(getattr(feat, "max_val", None))
    return Atom(col=name, op="in", val=[mn, mx])


def mine_state(
    slice_df: pd.DataFrame,
    feature_cols: list[str],
    cfg: MinerConfig,
) -> list[MinedRule]:
    """Run NiaARM on the slice; return rules passing the quality filter."""
    from niaarm import Dataset, get_rules
    from niapy.algorithms.basic import ParticleSwarmAlgorithm

    cols = [c for c in feature_cols if c in slice_df.columns]
    if not cols:
        return []
    df = slice_df[cols].copy().reset_index(drop=True)
    dataset = Dataset(df)
    algo = ParticleSwarmAlgorithm(seed=cfg.seed)
    res = get_rules(dataset, algo, ["support", "confidence"],
                    max_evals=cfg.max_evals)
    raw_rules = res.rules

    out: list[MinedRule] = []
    for i, r in enumerate(raw_rules):
        sup = float(getattr(r, "support", 0.0))
        conf = float(getattr(r, "confidence", 0.0))
        if conf < cfg.confidence_min or sup < cfg.support_min:
            continue
        lift = float(getattr(r, "lift", 0.0) or 0.0)
        ant = [_atom_from_feature(f) for f in r.antecedent]
        con = [_atom_from_feature(f) for f in r.consequent]
        out.append(MinedRule(
            id=f"r{i}", antecedent=ant, consequent=con,
            support=sup, confidence=conf, lift=lift,
        ))
    return out
