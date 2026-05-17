from gfsm.signatures import Condition, parse_atomic_condition_str
from gfsm.signatures import And, Atomic, Not, Or, negate_condition


def test_condition_to_string():
    assert Condition("H", "=", "Input").to_string() == "H = Input"


def test_parse_simple_eq():
    c = parse_atomic_condition_str("A = 1")
    assert (c.variable, c.operator, c.value) == ("A", "=", "1")


def test_parse_le_before_lt_and_eq():
    c = parse_atomic_condition_str("A <= 10")
    assert (c.variable, c.operator, c.value) == ("A", "<=", "10")


def test_parse_ne():
    c = parse_atomic_condition_str("T1 <> low")
    assert (c.variable, c.operator, c.value) == ("T1", "<>", "low")


def test_parse_strips_outer_parens_and_value_parens():
    c = parse_atomic_condition_str("(A = (5))")
    assert (c.variable, c.operator, c.value) == ("A", "=", "5")


def test_parse_no_operator_returns_none():
    assert parse_atomic_condition_str("justavar") is None


def test_negation_table_all_flips():
    pairs = {"=": "<>", "<>": "=", "<": ">=", "<=": ">",
             ">": "<=", ">=": "<", "??": "="}
    for src, dst in pairs.items():
        c = Condition("V", src, "1")
        assert negate_condition(c) == Condition("V", dst, "1")


def test_not_atomic_dnf():
    e = Not(Atomic(Condition("A", "=", "1")))
    assert e.to_dnf() == [[Condition("A", "<>", "1")]]


def test_not_and_is_or_of_negations():
    e = Not(And(Atomic(Condition("A", "=", "1")),
                Atomic(Condition("B", "=", "2"))))
    assert e.to_dnf() == [
        [Condition("A", "<>", "1")],
        [Condition("B", "<>", "2")],
    ]


def test_not_or_is_and_of_negations():
    e = Not(Or(Atomic(Condition("A", "=", "1")),
               Atomic(Condition("B", "=", "2"))))
    assert e.to_dnf() == [
        [Condition("A", "<>", "1"), Condition("B", "<>", "2")],
    ]


def test_double_negation():
    e = Not(Not(Atomic(Condition("A", "=", "1"))))
    assert e.to_dnf() == [[Condition("A", "=", "1")]]
