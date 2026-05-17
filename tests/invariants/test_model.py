import pytest

from invariants.model import Atom, InvariantsError, MinedRule


def test_error_is_exception():
    with pytest.raises(InvariantsError, match="boom"):
        raise InvariantsError("boom")


def test_atom_roundtrip():
    a = Atom(col="t41", op=">=", val=1.5)
    assert a.col == "t41" and a.op == ">=" and a.val == 1.5


def test_mined_rule_to_dict_shape():
    r = MinedRule(
        id="r0",
        antecedent=[Atom("t41", ">=", 1.2)],
        consequent=[Atom("p78", "==", 1.0)],
        support=0.83, confidence=0.92, lift=1.15,
    )
    d = r.to_dict()
    assert d["id"] == "r0"
    assert d["antecedent"] == [{"col": "t41", "op": ">=", "val": 1.2}]
    assert d["consequent"] == [{"col": "p78", "op": "==", "val": 1.0}]
    assert d["support"] == 0.83 and d["confidence"] == 0.92 and d["lift"] == 1.15
