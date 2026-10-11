"""Banker's algorithm: is a system state safe? (OS deadlock avoidance).

Two independent solvers:
  * ``_safe_fixpoint``: repeatedly admit any process whose remaining need fits.
  * ``_safe_greedy_closure``: same idea expressed as a work/need set-difference
    loop with an explicit visited set.
Both must agree on safe/unsafe for thousands of random states.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from edgen.foundry.generator import Answer, BaseGenerator, Distractor, Instance, ParamSpec


def _state(params: dict[str, Any]) -> tuple[list[int], list[list[int]], list[list[int]]]:
    return params["available"], params["allocation"], params["max"]


def _need(allocation: list[list[int]], maximum: list[list[int]]) -> list[list[int]]:
    return [[maximum[i][j] - allocation[i][j] for j in range(len(allocation[i]))] for i in range(len(allocation))]


def _safe_fixpoint(params: dict[str, Any]) -> Answer:
    available, allocation, maximum = _state(params)
    need = _need(allocation, maximum)
    work = list(available)
    finished = [False] * len(allocation)
    progressed = True
    while progressed:
        progressed = False
        for i in range(len(allocation)):
            if not finished[i] and all(need[i][j] <= work[j] for j in range(len(work))):
                for j in range(len(work)):
                    work[j] += allocation[i][j]
                finished[i] = True
                progressed = True
    safe = all(finished)
    return Answer(value=safe, display="safe" if safe else "unsafe", comparable=safe)


def _safe_greedy_closure(params: dict[str, Any]) -> Answer:
    available, allocation, maximum = _state(params)
    need = _need(allocation, maximum)
    work = list(available)
    remaining = set(range(len(allocation)))
    changed = True
    while changed and remaining:
        changed = False
        for i in sorted(remaining):
            if all(need[i][j] <= work[j] for j in range(len(work))):
                for j in range(len(work)):
                    work[j] += allocation[i][j]
                remaining.discard(i)
                changed = True
    safe = not remaining
    return Answer(value=safe, display="safe" if safe else "unsafe", comparable=safe)


class BankersAlgorithmGenerator(BaseGenerator):
    id = "bankers_safe"
    version = 1
    title = "Banker's algorithm: is the state safe?"
    node_id = "cs.os.deadlock_bankers"
    params = [ParamSpec(name="n_proc", lo=2, hi=4), ParamSpec(name="n_res", lo=2, hi=3)]
    bucket = 3

    def sample_params(self, seed: int) -> dict[str, Any]:
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        p = rng.randint(2, 4)
        r = rng.randint(2, 3)
        allocation = [[rng.randint(0, 2) for _ in range(r)] for _ in range(p)]
        maximum = [[allocation[i][j] + rng.randint(0, 3) for j in range(r)] for i in range(p)]
        # Available = total resources minus what is currently allocated.
        total = [rng.randint(2, 6) for _ in range(r)]
        available = [max(0, total[j] - sum(allocation[i][j] for i in range(p))) for j in range(r)]
        return {"available": available, "allocation": allocation, "max": maximum}

    @property
    def solvers(self) -> tuple[Callable[..., Answer], Callable[..., Answer]]:
        return _safe_fixpoint, _safe_greedy_closure

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        p = len(params["allocation"])
        # process count p; resource count r derived above
        rows = []
        for i in range(p):
            rows.append(
                f"P{i}: alloc={params['allocation'][i]}, max={params['max'][i]}"
            )
        stem = (
            f"Available={params['available']}. " + "; ".join(rows) + ". Is the state safe?"
        )
        return Instance(
            generator_id=self.id,
            version=self.version,
            seed=seed,
            params=params,
            stem=stem,
            bucket=self.bucket,
        )

    def distractors(self, params: dict[str, Any], answer: Answer) -> list[Distractor]:
        # The only binary mistake is inverting the verdict; tag it as such.
        if answer.comparable is True:
            return [Distractor(value=False, display="unsafe", error_tag="bankers_false_unsafe",
                               rationale="Concluded unsafe by missing a completing process order.")]
        return [Distractor(value=True, display="safe", error_tag="bankers_false_safe",
                           rationale="Concluded safe without a valid completion sequence.")]
