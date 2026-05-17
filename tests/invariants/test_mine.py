import json

import pandas as pd

from invariants.mine import MinerConfig, mine_state
from invariants.model import MinedRule


def test_mine_state_returns_filtered_json_serializable_rules():
    df = pd.DataFrame({
        "t1": [1.0, 1.1, 1.0, 1.2, 1.0, 1.1, 1.0, 1.0, 1.1, 1.2] * 8,
        "p1": [0,   0,   0,   0,   0,   0,   0,   0,   0,   0  ] * 8,
        "f1": [0.5, 0.6, 0.5, 0.7, 0.5, 0.6, 0.5, 0.5, 0.6, 0.7] * 8,
    })
    cfg = MinerConfig(max_evals=300, confidence_min=0.7, support_min=0.1,
                      seed=42)
    rules = mine_state(df, feature_cols=["t1", "p1", "f1"], cfg=cfg)
    assert isinstance(rules, list)
    for r in rules:
        assert isinstance(r, MinedRule)
        assert r.confidence >= 0.7
        assert r.support >= 0.1
    # Every rule must be JSON-serializable (native floats, no numpy scalars):
    json.dumps([r.to_dict() for r in rules])


def test_mine_state_empty_feature_cols_returns_empty():
    df = pd.DataFrame({"a": [1, 2, 3]})
    cfg = MinerConfig(max_evals=100, seed=42)
    assert mine_state(df, feature_cols=["nonexistent"], cfg=cfg) == []
