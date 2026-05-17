from gfsm.signatures import Condition, parse_atomic_condition_str
from gfsm.signatures import And, Atomic, Not, Or, negate_condition
from gfsm.signatures import parse_expr, tokenize


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


def test_distribute_and_over_or():
    # (A=1 OR B=2) AND (C=3 OR D=4)
    e = And(
        Or(Atomic(Condition("A", "=", "1")), Atomic(Condition("B", "=", "2"))),
        Or(Atomic(Condition("C", "=", "3")), Atomic(Condition("D", "=", "4"))),
    )
    assert e.to_dnf() == [
        [Condition("A", "=", "1"), Condition("C", "=", "3")],
        [Condition("A", "=", "1"), Condition("D", "=", "4")],
        [Condition("B", "=", "2"), Condition("C", "=", "3")],
        [Condition("B", "=", "2"), Condition("D", "=", "4")],
    ]


def test_or_concatenates():
    e = Or(Atomic(Condition("A", "=", "1")), Atomic(Condition("B", "=", "2")))
    assert e.to_dnf() == [
        [Condition("A", "=", "1")],
        [Condition("B", "=", "2")],
    ]


def test_plain_and_single_conjunction():
    e = And(Atomic(Condition("A", "=", "1")), Atomic(Condition("B", "=", "2")))
    assert e.to_dnf() == [[Condition("A", "=", "1"), Condition("B", "=", "2")]]


def test_tokenize_keywords_and_condition():
    toks = tokenize("A = 1 AND B = 2")
    kinds = [t[0] for t in toks]
    assert kinds == ["COND", "AND", "COND"]
    assert toks[0][1].strip() == "A = 1"
    assert toks[2][1].strip() == "B = 2"


def test_tokenize_word_boundary_not_keyword():
    # ANDREW must not tokenize as AND.
    toks = tokenize("ANDREW = 1")
    assert [t[0] for t in toks] == ["COND"]


def test_parse_simple_and_dnf():
    expr = parse_expr(tokenize("A = 1 AND B = 2"))
    assert expr.to_dnf() == [
        [Condition("A", "=", "1"), Condition("B", "=", "2")]
    ]


def test_parse_simple_or_dnf():
    expr = parse_expr(tokenize("A = 1 OR B = 2"))
    assert expr.to_dnf() == [
        [Condition("A", "=", "1")], [Condition("B", "=", "2")]
    ]


def test_parse_paren_precedence():
    expr = parse_expr(tokenize("(A = 1 OR B = 2) AND C = 3"))
    assert expr.to_dnf() == [
        [Condition("A", "=", "1"), Condition("C", "=", "3")],
        [Condition("B", "=", "2"), Condition("C", "=", "3")],
    ]
