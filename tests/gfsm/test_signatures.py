from gfsm.signatures import Condition, parse_atomic_condition_str


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
