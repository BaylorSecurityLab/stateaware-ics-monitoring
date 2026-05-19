import numpy as np
import pandas as pd

from invariants.rule_eval import atom_holds, all_hold, row_violation_count


def _row(d):
    return pd.Series(d)


def test_atom_holds_in_range_and_ops():
    r = _row({"a": 1.0, "b": 5})
    assert atom_holds(r, {"col": "a", "op": "in", "val": [0.0, 2.0]})
    assert not atom_holds(r, {"col": "a", "op": "in", "val": [2.0, 3.0]})
    assert atom_holds(r, {"col": "b", "op": ">=", "val": 5})
    assert not atom_holds(r, {"col": "b", "op": ">", "val": 5})
    assert not atom_holds(r, {"col": "zzz", "op": "==", "val": 1})


def test_all_hold_empty_is_true():
    assert all_hold(_row({"a": 1}), []) is True


def test_row_violation_count():
    r = _row({"x": 10.0})
    rules = [
        {"antecedent": [{"col": "x", "op": "in", "val": [0.0, 20.0]}],
         "consequent": [{"col": "x", "op": "in", "val": [0.0, 5.0]}]},
        {"antecedent": [{"col": "x", "op": "in", "val": [100.0, 200.0]}],
         "consequent": [{"col": "x", "op": "in", "val": [0.0, 1.0]}]},
        {"antecedent": [{"col": "x", "op": "in", "val": [0.0, 20.0]}],
         "consequent": [{"col": "x", "op": "in", "val": [0.0, 20.0]}]},
    ]
    assert row_violation_count(r, rules) == 1


def _scalar_counts(df, rules):
    return np.array(
        [row_violation_count(df.iloc[i], rules) for i in range(len(df))],
        dtype=int,
    )


def test_frame_violation_counts_matches_scalar_randomized():
    from invariants.rule_eval import frame_violation_counts
    rng = np.random.default_rng(1234)
    for _ in range(25):
        n = int(rng.integers(1, 40))
        df = pd.DataFrame({
            "a": rng.normal(size=n),
            "b": rng.integers(0, 5, size=n).astype(float),
            "c": rng.normal(size=n),
        })
        mask = rng.random(n) < 0.15
        df.loc[mask, "a"] = np.nan
        rules = []
        for _r in range(int(rng.integers(0, 6))):
            def _atom():
                col = rng.choice(["a", "b", "c", "missing"])
                op = rng.choice(["in", "==", ">=", "<=", ">", "<"])
                if op == "in":
                    lo, hi = sorted(rng.normal(size=2).tolist())
                    val = [lo, hi]
                else:
                    val = float(rng.normal())
                return {"col": str(col), "op": str(op), "val": val}
            rules.append({
                "antecedent": [_atom()
                               for _ in range(int(rng.integers(0, 3)))],
                "consequent": [_atom()
                               for _ in range(int(rng.integers(1, 3)))],
            })
        got = frame_violation_counts(df, rules)
        exp = _scalar_counts(df, rules)
        assert np.array_equal(got, exp), (rules, got, exp)


def test_frame_violation_counts_in_op_nan_holds_like_scalar():
    from invariants.rule_eval import frame_violation_counts
    df = pd.DataFrame({"x": [float("nan"), 10.0]})
    rules = [{"antecedent": [],
              "consequent": [{"col": "x", "op": "in", "val": [0.0, 5.0]}]}]
    got = frame_violation_counts(df, rules)
    exp = _scalar_counts(df, rules)
    assert list(got) == list(exp) == [0, 1]


def test_frame_violation_counts_empty():
    from invariants.rule_eval import frame_violation_counts
    assert list(frame_violation_counts(pd.DataFrame({"x": []}), [])) == []
    df = pd.DataFrame({"x": [1.0, 2.0]})
    assert list(frame_violation_counts(df, [])) == [0, 0]
