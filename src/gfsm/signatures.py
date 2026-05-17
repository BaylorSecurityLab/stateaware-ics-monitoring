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
