"""Problem Foundry — generators whose answers come from verified code (ADR 8).

The LLM writes generator code, not questions. Trust = two independently written
solvers agree on 10k+ seeds + property tests + hand-verified golden cases +
one-time human review before publish.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Step:
    """One line of the oracle trace used by Reasoning-Diff (architecture §11)."""

    text: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MistakeModel:
    """A wrong answer produced by a *known* student mistake — tagged for diagnosis."""

    tag: str
    title: str
    answer: Any
    feedback: str


@runtime_checkable
class Generator(Protocol):
    id: str
    node_ids: list[str]
    title: str
    input_spec: dict[str, Any]  # {kind: number|text|choice, options?, placeholder?, hint?}
    hints: list[str]  # ladder of 4 — never answer-first (IdeaBrief §8)

    def sample(self, rng, difficulty: int) -> dict[str, Any]: ...
    def statement(self, params: dict[str, Any]) -> str: ...
    def node_for(self, params: dict[str, Any]) -> str: ...
    def solve_a(self, params: dict[str, Any]) -> Any: ...
    def solve_b(self, params: dict[str, Any]) -> Any: ...
    def canonical(self, answer: Any) -> str: ...
    def check(self, params: dict[str, Any], answer: Any) -> bool: ...
    def trace(self, params: dict[str, Any]) -> list[Step]: ...
    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]: ...
    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]: ...
    def agree(self, params: dict[str, Any], a: Any, b: Any) -> bool: ...


class BaseGenerator:
    """Shared defaults: equality-based checking, empty properties."""

    id = "base"
    node_ids: list[str] = []
    title = ""
    input_spec: dict[str, Any] = {"kind": "text"}
    hints: list[str] = []

    def node_for(self, params: dict[str, Any]) -> str:
        return self.node_ids[0]

    def canonical(self, answer: Any) -> str:
        if isinstance(answer, bool):
            return "true" if answer else "false"
        if isinstance(answer, float):
            return f"{answer:.2f}"
        if isinstance(answer, int):
            return str(answer)
        return str(answer).strip()

    def answer_key(self, params: dict[str, Any], answer: Any) -> str:
        """Canonical string for golden comparisons (mode-aware gens override)."""
        return self.canonical(answer)

    def check(self, params: dict[str, Any], answer: Any) -> bool:
        return self.canonical(answer) == self.canonical(params["_key"]) if "_key" in params else False

    def agree(self, params: dict[str, Any], a: Any, b: Any) -> bool:
        return self.canonical(a) == self.canonical(b)

    def properties(self, params: dict[str, Any], answer: Any) -> list[tuple[str, bool]]:
        return []

    def mistakes(self, params: dict[str, Any]) -> list[MistakeModel]:
        return []

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def grade_numeric(key: float, submitted: Any, tol: float = 0.011) -> bool:
        try:
            return abs(float(str(submitted).replace(",", "")) - float(key)) <= tol
        except (TypeError, ValueError):
            return False


# --- registry ---------------------------------------------------------------

_REGISTRY: dict[str, Generator] = {}


def register(gen: Generator) -> Generator:
    if gen.id in _REGISTRY and _REGISTRY[gen.id] is not gen:
        raise ValueError(f"duplicate generator id {gen.id}")
    _REGISTRY[gen.id] = gen
    return gen


def get_generator(gen_id: str) -> Generator:
    try:
        return _REGISTRY[gen_id]
    except KeyError:
        raise KeyError(f"unknown generator: {gen_id}") from None


def all_generators() -> list[Generator]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]
