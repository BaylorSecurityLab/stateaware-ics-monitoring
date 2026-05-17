from gfsm.signatures import Condition, parse_atomic_condition_str
from gfsm.signatures import And, Atomic, Not, Or, negate_condition
from gfsm.signatures import parse_expr, tokenize
from gfsm.signatures import conjunction_is_unsat, is_syntactically_unsat


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


def test_no_check_is_empty_conjunction():
    from gfsm.signatures import parse_transition_condition
    assert parse_transition_condition("No Check") == [[]]
    assert parse_transition_condition("") == [[]]


def test_simple_and():
    from gfsm.signatures import parse_transition_condition
    dnf = parse_transition_condition("A = 1 AND B = 2")
    assert len(dnf) == 1 and len(dnf[0]) == 2


def test_simple_or():
    from gfsm.signatures import parse_transition_condition
    dnf = parse_transition_condition("A = 1 OR B = 2")
    assert len(dnf) == 2


def test_dedupe_within_conjunction():
    from gfsm.signatures import parse_transition_condition
    dnf = parse_transition_condition("A = 1 AND A = 1")
    assert dnf == [[Condition("A", "=", "1")]]


from gfsm.model import FunctionBlock, State, Transition
from gfsm.signatures import (
    PathSignature,
    StateSignature,
    StateSignatureTable,
    generate_signatures,
)


def _multi_path_fsm() -> FunctionBlock:
    fb = FunctionBlock.new("MultiPathFB", "state")
    for s in ("10", "20", "30"):
        fb.add_state(State.new(s))
    fb.add_transition(Transition.new("10", "20", "sensor = low"))
    fb.add_transition(Transition.new("10", "20", "button = pressed"))
    fb.add_transition(Transition.new("20", "30", "timer > 100"))
    return fb


def test_multiple_path_signatures():
    table = generate_signatures(_multi_path_fsm())
    assert len(table.signatures["20"].path_signatures) == 2


def test_initial_state_signature_is_marker():
    table = generate_signatures(_multi_path_fsm())
    assert table.signatures["10"].format_conditions() == "[initial]"


def test_path_signature_sorted_and_deduped():
    fb = FunctionBlock.new("FB", "state")
    for s in ("10", "20"):
        fb.add_state(State.new(s))
    fb.add_transition(Transition.new("10", "20", "B = 2 AND A = 1"))
    table = generate_signatures(fb)
    sig = table.signatures["20"].path_signatures[0]
    assert [c.to_string() for c in sig.conditions] == ["A = 1", "B = 2"]


def test_or_condition_two_signatures():
    fb = FunctionBlock.new("OrFB", "state")
    for s in ("10", "20"):
        fb.add_state(State.new(s))
    fb.add_transition(
        Transition.new("10", "20", "sensor = low OR button = pressed")
    )
    table = generate_signatures(fb)
    assert len(table.signatures["20"].path_signatures) == 2


def test_equal_different_values_unsat():
    assert conjunction_is_unsat(
        [Condition("T1", "=", "high"), Condition("T1", "=", "low")]
    )


def test_equal_same_value_sat():
    assert not conjunction_is_unsat(
        [Condition("T1", "=", "high"), Condition("T1", "=", "high")]
    )


def test_equal_and_neq_same_value_unsat():
    assert conjunction_is_unsat(
        [Condition("T1", "=", "high"), Condition("T1", "<>", "high")]
    )


def test_numeric_range_contradiction_unsat():
    assert conjunction_is_unsat(
        [Condition("x", ">", "5"), Condition("x", "<", "3")]
    )
    assert conjunction_is_unsat(
        [Condition("x", ">", "5"), Condition("x", "=", "1")]
    )


def test_numeric_range_satisfiable():
    assert not conjunction_is_unsat(
        [Condition("x", ">", "1"), Condition("x", "<", "10")]
    )


def test_different_variables_independent_sat():
    assert not conjunction_is_unsat(
        [Condition("A", "=", "1"), Condition("B", "=", "2")]
    )


def test_dnf_unsat_only_if_all_terms_unsat():
    sat_term = [Condition("A", "=", "1")]
    unsat_term = [Condition("A", "=", "1"), Condition("A", "=", "2")]
    assert is_syntactically_unsat([unsat_term, unsat_term])
    assert not is_syntactically_unsat([unsat_term, sat_term])
    assert not is_syntactically_unsat([[]])  # empty conj = TRUE
