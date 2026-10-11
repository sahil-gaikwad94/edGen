"""Attribute closure (DBMS normalization) — verified generator.

Two independent solvers compute X+:
  * ``_closure_fixpoint``: global scan-to-fixpoint over the FD set.
  * ``_closure_worklist``: per-attribute worklist that revisits only FDs whose
    LHS gained a member.
Agreement across thousands of seeds is the trust signal (ADR #8).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from edgen.foundry.generator import Answer, BaseGenerator, Distractor, Instance, ParamSpec

_ATTRS = ["A", "B", "C", "D", "E", "F"]


def _parse(params: dict[str, Any]) -> tuple[list[str], list[tuple[set[str], set[str]]], set[str]]:
    fds = [(set(lhs), set(rhs)) for lhs, rhs in params["fds"]]
    return params["attrs"], fds, set(params["start"])


def _closure_fixpoint(params: dict[str, Any]) -> Answer:
    _, fds, start = _parse(params)
    result = set(start)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            if lhs <= result and not rhs <= result:
                result |= rhs
                changed = True
    key = "".join(sorted(result))
    return Answer(value=key, display=key, comparable=key)


def _closure_worklist(params: dict[str, Any]) -> Answer:
    _, fds, start = _parse(params)
    result = set(start)
    queue = list(start)
    while queue:
        a = queue.pop()
        for lhs, rhs in fds:
            if a in lhs and lhs <= result:
                add = rhs - result
                if add:
                    result |= add
                    queue.extend(add)
    key = "".join(sorted(result))
    return Answer(value=key, display=key, comparable=key)


class FDClosureGenerator(BaseGenerator):
    id = "fd_closure"
    version = 1
    title = "Attribute closure of a functional dependency set"
    node_id = "dbms.normalization.fd_closure"
    params = [ParamSpec(name="n_attrs", lo=3, hi=5), ParamSpec(name="n_fds", lo=2, hi=5)]
    bucket = 2

    def sample_params(self, seed: int) -> dict[str, Any]:
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        n = rng.randint(3, 5)
        attrs = _ATTRS[:n]
        fds: list[list[str]] = []
        for _ in range(rng.randint(2, 5)):
            lhs = sorted(rng.sample(attrs, rng.randint(1, min(2, n))))
            pool = [a for a in attrs if a not in lhs]
            rhs = sorted(rng.sample(pool, rng.randint(1, min(2, len(pool)))))
            fds.append(["".join(lhs), "".join(rhs)])
        if not fds:
            fds = [[attrs[0], attrs[1]]]
        start = sorted(rng.sample(attrs, rng.randint(1, min(2, n))))
        return {"attrs": attrs, "fds": fds, "start": start}

    @property
    def solvers(self) -> tuple[Callable[..., Answer], Callable[..., Answer]]:
        return _closure_fixpoint, _closure_worklist

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        attrs = params["attrs"]
        fds_txt = ", ".join(f"{lhs} \u2192 {rhs}" for lhs, rhs in params["fds"])
        start = "".join(params["start"])
        stem = (
            f"Relation R({' '.join(attrs)}) with FDs: {fds_txt}. "
            f"Compute the attribute closure ({start})+."
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
        _, fds, start = _parse(params)
        one_step = set(start)
        for lhs, rhs in fds:
            if lhs <= one_step:
                one_step |= rhs
        all_rhs = set(start)
        for _, rhs in fds:
            all_rhs |= rhs
        all_attrs = set(params["attrs"])
        out: list[Distractor] = []
        seen = {answer.comparable}
        for s, tag, why in [
            (one_step, "closure_one_step", "Stops after one derivation step; misses transitive FDs."),
            (all_rhs, "closure_over_union", "Unions every RHS instead of only reachable ones."),
            (all_attrs, "closure_all_attrs", "Assumes the closure is the whole schema."),
        ]:
            key = "".join(sorted(s))
            if key not in seen:
                seen.add(key)
                out.append(Distractor(value=key, display=key, error_tag=tag, rationale=why))
        return out
