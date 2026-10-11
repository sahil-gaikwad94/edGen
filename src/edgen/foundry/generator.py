"""Foundry generator contract.

A :class:`Generator` owns three things:

1. ``params`` — the sampled parameter space (seeds are deterministic).
2. ``solvers`` — two *independently written* functions that compute the answer.
   Agreement between them is the trust signal (never LLM consensus, ADR #8).
3. ``distractors`` — plausible wrong answers tagged with the mistake they encode,
   so a wrong pick can be diagnosed.

Generators are pure: given the same seed they must return the same instance.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ParamSpec(BaseModel):
    """Declares one sampled parameter and its integer range (inclusive)."""

    name: str
    lo: int
    hi: int

    def sample(self, rng: random.Random) -> int:
        return rng.randint(self.lo, self.hi)


class Instance(BaseModel):
    """A concrete, reproducible problem instance.

    ``params`` fully determines the problem, so ``instance_id`` is a content hash
    and the same seed always yields the same instance across processes.
    """

    generator_id: str
    version: int
    seed: int
    params: dict[str, Any]
    stem: str
    #: Optional structured payload for labs/visualizers (e.g. reference sequence).
    payload: dict[str, Any] = Field(default_factory=dict)
    #: Difficulty bucket 0..4 (IRT-calibrated once data exists).
    bucket: int = 2

    @property
    def instance_id(self) -> str:
        raw = f"{self.generator_id}@{self.version}:{self.seed}:{sorted(self.params.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


class Answer(BaseModel):
    """The verified answer to an instance."""

    value: Any
    #: Canonical text form shown to the learner.
    display: str
    #: Machine-comparable form used for grading (str/int/float/list).
    comparable: Any = None

    def model_post_init(self, _ctx: Any) -> None:  # noqa: D105
        if self.comparable is None:
            object.__setattr__(self, "comparable", self.value)


class Distractor(BaseModel):
    """A wrong answer plus the misconception it represents."""

    value: Any
    display: str
    error_tag: str
    #: Why a learner picks this (used for step-level diagnosis / misconception cards).
    rationale: str = ""


@runtime_checkable
class Generator(Protocol):
    """Structural contract for a Foundry generator."""

    id: str
    version: int
    title: str
    node_id: str
    params: list[ParamSpec]
    #: Two independent solvers. Both are pure ``params -> Answer``.
    solvers: tuple[Callable[[dict[str, Any]], Answer], Callable[[dict[str, Any]], Answer]]

    def build(self, seed: int, params: dict[str, Any]) -> Instance: ...

    def distractors(self, params: dict[str, Any], answer: Answer) -> list[Distractor]: ...


class BaseGenerator:
    """Convenience base class implementing the boilerplate of :class:`Generator`.

    Subclasses set ``id/version/title/node_id/params`` and implement
    ``solvers``, ``build``, ``distractors``.
    """

    id: str = ""
    version: int = 1
    title: str = ""
    node_id: str = ""
    params: list[ParamSpec] = []
    bucket: int = 2

    @property
    def solvers(self) -> tuple[Callable[[dict[str, Any]], Answer], Callable[[dict[str, Any]], Answer]]:
        raise NotImplementedError

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        raise NotImplementedError

    def distractors(self, params: dict[str, Any], answer: Answer) -> list[Distractor]:
        return []

    def sample_params(self, seed: int) -> dict[str, Any]:
        """Deterministically sample a parameter set from a seed."""
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        return {p.name: p.sample(rng) for p in self.params}

    def instance(self, seed: int) -> Instance:
        params = self.sample_params(seed)
        inst = self.build(seed, params)
        return inst

    def solve(self, seed: int) -> tuple[Instance, Answer, list[Distractor]]:
        """Full deterministic path: instance -> verified answer -> distractors."""
        inst = self.instance(seed)
        answer = self.solvers[0](inst.params)
        return inst, answer, self.distractors(inst.params, answer)
