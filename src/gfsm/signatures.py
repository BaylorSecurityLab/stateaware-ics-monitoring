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
