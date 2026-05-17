"""Data model and exception types for the invariants stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvariantsError(Exception):
    """Unrecoverable invariants-stage error (missing inputs, etc.)."""


@dataclass(frozen=True)
class Atom:
    """A single column-op-value predicate, e.g. (t41, >=, 1.2)."""
    col: str
    op: str
    val: Any

    def to_dict(self) -> dict[str, Any]:
        return {"col": self.col, "op": self.op, "val": self.val}


@dataclass
class MinedRule:
    """A NiaARM rule, antecedent ⇒ consequent, with quality metrics."""
    id: str
    antecedent: list[Atom]
    consequent: list[Atom]
    support: float
    confidence: float
    lift: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "antecedent": [a.to_dict() for a in self.antecedent],
            "consequent": [a.to_dict() for a in self.consequent],
            "support": self.support,
            "confidence": self.confidence,
            "lift": self.lift,
        }


# alias for the persisted Φ mapping
InvariantMapping = dict[str, list[MinedRule]]
