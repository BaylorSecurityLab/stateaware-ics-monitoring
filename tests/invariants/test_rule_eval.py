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
