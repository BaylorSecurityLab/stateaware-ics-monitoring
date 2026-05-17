"""State signatures + DNF. Faithful port of src/analysis/signatures.rs.

Deliberate port deviation for determinism (a hard project requirement):
`merge_equivalent_signatures` returns dict-insertion order instead of
Rust's unspecified `HashMap::into_values()` order. Downstream sorts anyway.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    variable: str
    operator: str
    value: str

    def to_string(self) -> str:
        return f"{self.variable} {self.operator} {self.value}"


def parse_atomic_condition_str(expr: str) -> "Condition | None":
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1]
    operators = ["<=", ">=", "<>", "=", "<", ">"]
    for op in operators:
        pos = expr.find(op)
        if pos != -1:
            variable = expr[:pos].strip()
            value = expr[pos + len(op):].strip()
            if value.startswith("(") and value.endswith(")"):
                value = value[1:-1].strip()
            return Condition(variable, op, value)
    return None


def negate_condition(cond: Condition) -> Condition:
    table = {"=": "<>", "<>": "=", "<": ">=", "<=": ">", ">": "<=", ">=": "<"}
    return Condition(cond.variable, table.get(cond.operator, "="), cond.value)


class BooleanExpr:
    def to_dnf(self) -> list[list[Condition]]:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass
class Atomic(BooleanExpr):
    cond: Condition

    def to_dnf(self) -> list[list[Condition]]:
        return [[self.cond]]


@dataclass
class And(BooleanExpr):
    left: BooleanExpr
    right: BooleanExpr

    def to_dnf(self) -> list[list[Condition]]:
        left_dnf = self.left.to_dnf()
        right_dnf = self.right.to_dnf()
        result: list[list[Condition]] = []
        for lt in left_dnf:
            for rt in right_dnf:
                result.append([*lt, *rt])
        return result


@dataclass
class Or(BooleanExpr):
    left: BooleanExpr
    right: BooleanExpr

    def to_dnf(self) -> list[list[Condition]]:
        return [*self.left.to_dnf(), *self.right.to_dnf()]


@dataclass
class Not(BooleanExpr):
    inner: BooleanExpr

    def to_dnf(self) -> list[list[Condition]]:
        inner = self.inner
        if isinstance(inner, Atomic):
            return [[negate_condition(inner.cond)]]
        if isinstance(inner, And):
            return Or(Not(inner.left), Not(inner.right)).to_dnf()
        if isinstance(inner, Or):
            return And(Not(inner.left), Not(inner.right)).to_dnf()
        if isinstance(inner, Not):
            return inner.inner.to_dnf()
        raise NotImplementedError


def _check_keyword(s: str, pos: int, kw: str) -> bool:
    if pos + len(kw) > len(s):
        return False
    if s[pos:pos + len(kw)] != kw:
        return False
    nxt = pos + len(kw)
    if nxt < len(s):
        c = s[nxt]
        if c.isalnum() or c == "_":
            return False
    return True


def tokenize(expr: str) -> list[tuple[str, str | None]]:
    tokens: list[tuple[str, str | None]] = []
    pos = 0
    n = len(expr)
    while pos < n:
        while pos < n and expr[pos].isspace():
            pos += 1
        if pos >= n:
            break
        if _check_keyword(expr, pos, "AND"):
            tokens.append(("AND", None))
            pos += 3
        elif _check_keyword(expr, pos, "OR"):
            tokens.append(("OR", None))
            pos += 2
        elif _check_keyword(expr, pos, "NOT"):
            tokens.append(("NOT", None))
            pos += 3
        elif expr[pos] == "(":
            tokens.append(("LP", None))
            pos += 1
        elif expr[pos] == ")":
            tokens.append(("RP", None))
            pos += 1
        else:
            start = pos
            depth = 0
            while pos < n:
                ch = expr[pos]
                if ch == "(":
                    depth += 1
                    pos += 1
                elif ch == ")":
                    if depth > 0:
                        depth -= 1
                        pos += 1
                    else:
                        break
                elif depth == 0 and (
                    _check_keyword(expr, pos, "AND")
                    or _check_keyword(expr, pos, "OR")
                ):
                    break
                else:
                    pos += 1
            if pos > start:
                cond = expr[start:pos].strip()
                if cond:
                    tokens.append(("COND", cond))
                else:
                    pos += 1 if pos == start else 0
            else:
                pos += 1
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str | None]]) -> None:
        self.t = tokens
        self.i = 0

    def parse(self) -> BooleanExpr | None:
        return self._or()

    def _or(self) -> BooleanExpr | None:
        left = self._and()
        if left is None:
            return None
        while self.i < len(self.t) and self.t[self.i][0] == "OR":
            self.i += 1
            right = self._and()
            if right is None:
                return None
            left = Or(left, right)
        return left

    def _and(self) -> BooleanExpr | None:
        left = self._not()
        if left is None:
            return None
        while self.i < len(self.t) and self.t[self.i][0] == "AND":
            self.i += 1
            right = self._not()
            if right is None:
                return None
            left = And(left, right)
        return left

    def _not(self) -> BooleanExpr | None:
        if self.i < len(self.t) and self.t[self.i][0] == "NOT":
            self.i += 1
            inner = self._primary()
            if inner is None:
                return None
            return Not(inner)
        return self._primary()

    def _primary(self) -> BooleanExpr | None:
        if self.i >= len(self.t):
            return None
        kind, payload = self.t[self.i]
        if kind == "LP":
            self.i += 1
            expr = self._or()
            if self.i < len(self.t) and self.t[self.i][0] == "RP":
                self.i += 1
            return expr
        if kind == "COND":
            self.i += 1
            c = parse_atomic_condition_str(payload or "")
            return None if c is None else Atomic(c)
        return None


def parse_expr(tokens: list[tuple[str, str | None]]) -> BooleanExpr | None:
    return _Parser(tokens).parse()


def _parse_simple_condition(s: str) -> list[list[Condition]]:
    conds: list[Condition] = []
    for part in s.split(" AND "):
        c = parse_atomic_condition_str(part.strip())
        if c is not None:
            conds.append(c)
    return [conds]


def parse_transition_condition(condition_str: str) -> list[list[Condition]]:
    if condition_str == "" or condition_str == "No Check":
        return [[]]
    tokens = tokenize(condition_str)
    if not tokens:
        return [[]]
    expr = parse_expr(tokens)
    if expr is None:
        return _parse_simple_condition(condition_str)
    dnf = expr.to_dnf()
    result: list[list[Condition]] = []
    for conj in dnf:
        seen: set[tuple[str, str, str]] = set()
        unique: list[Condition] = []
        for c in conj:
            key = (c.variable, c.operator, c.value)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        result.append(unique)
    return result


from .model import FunctionBlock  # noqa: E402  (kept local to avoid cycle risk)


@dataclass
class PathSignature:
    conditions: list[Condition]
    path_id: int

    def format_conditions(self) -> str:
        if not self.conditions:
            return "[initial]"
        return " AND ".join(c.to_string() for c in self.conditions)


@dataclass
class StateSignature:
    state_id: str
    path_signatures: list[PathSignature]
    paths_count: int

    def format_conditions(self) -> str:
        if not self.path_signatures:
            return "[initial]"
        if len(self.path_signatures) == 1:
            return self.path_signatures[0].format_conditions()
        return " OR ".join(
            f"({ps.format_conditions()})" for ps in self.path_signatures
        )


@dataclass
class StateSignatureTable:
    function_block_name: str
    case_variable: str
    signatures: dict[str, StateSignature]


def _find_initial_states(fb: FunctionBlock) -> list[str]:
    return [s.id for s in fb.states.values() if not s.transitions_in]


def _fallback_initial(fb: FunctionBlock) -> list[str]:
    if "100" in fb.states:
        return ["100"]
    if "10" in fb.states:
        return ["10"]
    if fb.states:
        return [next(iter(fb.states.keys()))]
    return []


def _dfs(fb, current, visited, current_path, paths_to_states):
    paths_to_states.setdefault(current, []).append(list(current_path))
    visited.add(current)
    for idx, tr in enumerate(fb.transitions):
        if tr.from_state == current and tr.to_state not in visited:
            current_path.append((tr.to_state, idx))
            _dfs(fb, tr.to_state, visited, current_path, paths_to_states)
            current_path.pop()
    visited.discard(current)


def _find_all_paths(fb: FunctionBlock) -> dict[str, list[list[tuple[str, int | None]]]]:
    paths: dict[str, list[list[tuple[str, int | None]]]] = {}
    initial = _find_initial_states(fb) or _fallback_initial(fb)
    for init in initial:
        _dfs(fb, init, set(), [(init, None)], paths)
    return paths


def _cross_product_dnf(dnfs: list[list[list[Condition]]]) -> list[list[Condition]]:
    if not dnfs:
        return [[]]
    result = [list(c) for c in dnfs[0]]
    for dnf in dnfs[1:]:
        new_result: list[list[Condition]] = []
        for lt in result:
            for rt in dnf:
                new_result.append([*lt, *rt])
        result = new_result
    return result


def _extract_conditions_from_path(fb, path) -> list[list[Condition]]:
    transition_dnfs: list[list[list[Condition]]] = []
    for _state_id, tidx in path:
        if tidx is not None and 0 <= tidx < len(fb.transitions):
            transition_dnfs.append(
                parse_transition_condition(fb.transitions[tidx].condition)
            )
    return _cross_product_dnf(transition_dnfs)


def _remove_redundancy(conditions: list[Condition]) -> list[Condition]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Condition] = []
    for c in conditions:
        key = (c.variable, c.operator, c.value)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=lambda c: (c.variable, c.operator, c.value))
    return unique


def _merge_equivalent(sigs: list[PathSignature]) -> list[PathSignature]:
    if len(sigs) <= 1:
        return sigs
    grouped: dict[str, PathSignature] = {}
    for sig in sigs:
        key = sig.format_conditions()
        if key not in grouped:
            grouped[key] = sig
    return list(grouped.values())


def _build_signature_for_state(fb, state_id, paths) -> StateSignature:
    path_signatures: list[PathSignature] = []
    sig_id = 0
    for path in paths:
        for conditions in _extract_conditions_from_path(fb, path):
            path_signatures.append(
                PathSignature(_remove_redundancy(conditions), sig_id)
            )
            sig_id += 1
    return StateSignature(
        state_id=state_id,
        path_signatures=_merge_equivalent(path_signatures),
        paths_count=len(paths),
    )


def generate_signatures(fb: FunctionBlock) -> StateSignatureTable:
    table = StateSignatureTable(fb.name, fb.case_variable, {})
    for state_id, paths in _find_all_paths(fb).items():
        table.signatures[state_id] = _build_signature_for_state(
            fb, state_id, paths
        )
    return table


def _as_float(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def conjunction_is_unsat(conj: list[Condition]) -> bool:
    """Return True iff this single conjunction (one DNF term) is
    syntactically unsatisfiable.

    Detects contradictory constant comparisons on the *same* variable:
    two ``=`` with different values, ``=`` and ``<>`` with the same
    value, or an empty numeric interval (lo > hi, lo == hi with an open
    bound, or an equality pin lying outside ``[lo, hi]``). This is a
    purely syntactic check — no SMT solving is performed.
    """
    # Group every condition by the variable it constrains; contradictions
    # can only arise between conditions on the same variable.
    by_var: dict[str, list[Condition]] = {}
    for c in conj:
        by_var.setdefault(c.variable, []).append(c)

    for _var, conds in by_var.items():
        eq_values: set[str] = set()
        neq_values: set[str] = set()
        lo_bound = float("-inf")
        lo_closed = True
        hi_bound = float("inf")
        hi_closed = True
        eq_pinned: float | None = None

        for c in conds:
            op, val = c.operator, c.value
            fv = _as_float(val)
            if op == "=":
                # eq/neq cross-check: two distinct ``=`` values, or an
                # ``=`` value already forbidden by a ``<>``, is a clash.
                eq_values.add(val)
                if len(eq_values) > 1:
                    return True
                if val in neq_values:
                    return True
                if fv is not None:
                    if eq_pinned is not None and eq_pinned != fv:
                        return True
                    eq_pinned = fv
            elif op == "<>":
                # Mirror of the above: ``<>`` a value that ``=`` requires.
                neq_values.add(val)
                if val in eq_values:
                    return True
            elif fv is not None:
                # Tighten the running numeric interval [lo, hi]; only
                # adopt a bound when it is strictly more restrictive
                # (closed->open transition counts as tighter at equality).
                if op == ">":
                    if fv > lo_bound or (fv == lo_bound and lo_closed):
                        lo_bound, lo_closed = fv, False
                elif op == ">=":
                    if fv > lo_bound:
                        lo_bound, lo_closed = fv, True
                elif op == "<":
                    if fv < hi_bound or (fv == hi_bound and hi_closed):
                        hi_bound, hi_closed = fv, False
                elif op == "<=":
                    if fv < hi_bound:
                        hi_bound, hi_closed = fv, True

        # Final emptiness checks: crossed bounds, a degenerate point
        # interval with an open side, or an ``=`` pin outside [lo, hi].
        if lo_bound > hi_bound:
            return True
        if lo_bound == hi_bound and not (lo_closed and hi_closed):
            return True
        if eq_pinned is not None:
            if eq_pinned < lo_bound or (eq_pinned == lo_bound and not lo_closed):
                return True
            if eq_pinned > hi_bound or (eq_pinned == hi_bound and not hi_closed):
                return True
    return False


def is_syntactically_unsat(dnf: list[list[Condition]]) -> bool:
    """Return True iff the whole DNF is syntactically unsatisfiable.

    A DNF is unsat iff *every* conjunction term is unsat. An empty DNF
    ``[]`` is treated as unsat; ``[[]]`` (a single empty conjunction) is
    satisfiable, representing TRUE.
    """
    if not dnf:
        return True
    return all(conjunction_is_unsat(term) for term in dnf)
