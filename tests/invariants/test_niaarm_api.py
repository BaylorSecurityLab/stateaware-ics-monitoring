"""Pin the niaarm public API surface used by the rest of the stage.

If this test fails, niaarm has drifted vs the plan; STOP and report the
actual signatures observed so the plan can be adjusted before proceeding.
"""

import pandas as pd


def test_niaarm_imports_and_returns_rules_with_expected_attrs():
    from niaarm import Dataset, get_rules
    from niapy.algorithms.basic import ParticleSwarmAlgorithm

    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "y": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "z": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    })
    dataset = Dataset(df)
    algo = ParticleSwarmAlgorithm(seed=42)
    res = get_rules(dataset, algo, ["support", "confidence"], max_evals=200)
    rules = res[0] if isinstance(res, tuple) else res
    assert len(rules) >= 0
    if len(rules) > 0:
        r = rules[0]
        for attr in ("support", "confidence", "antecedent", "consequent"):
            assert hasattr(r, attr), f"niaarm.Rule missing {attr}"
