"""B+ tree height for a given number of keys (DBMS indexing).

Two independent solvers:
  * ``_height_iter``: iterative level-by-level node accounting.
  * ``_height_bisect``: height derived from the minimum fan-out bound via logs.
Both must agree; a mismatch means the generator's capacity assumptions are wrong.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any

from edgen.foundry.generator import Answer, BaseGenerator, Distractor, Instance, ParamSpec


def _nums(params: dict[str, Any]) -> tuple[int, int]:
    return params["order"], params["keys"]


def _height_iter(params: dict[str, Any]) -> Answer:
    order, keys = _nums(params)
    # Order p: internal nodes hold up to p pointers (p-1 keys); leaves hold up to
    # p-1 key/pointer pairs and at least ceil(p/2)-1 keys.
    min_leaf = max(1, math.ceil(order / 2) - 1)
    leaves = 1
    while leaves * min_leaf < keys:
        leaves += 1
    # Height counts leaf level as 0.
    h = 0
    pointers = leaves
    while pointers > 1:
        pointers = math.ceil(pointers / math.ceil(order / 2))
        h += 1
    return Answer(value=h, display=str(h), comparable=h)


def _height_bisect(params: dict[str, Any]) -> Answer:
    order, keys = _nums(params)
    min_leaf = max(1, math.ceil(order / 2) - 1)
    leaves = max(1, math.ceil(keys / min_leaf))
    if leaves == 1:
        return Answer(value=0, display="0", comparable=0)
    branch = math.ceil(order / 2)
    # log-based estimate, corrected with exact integer powers to avoid the
    # floating-point ceiling error at exact powers (e.g. log_5(125)).
    h = math.ceil(math.log(leaves) / math.log(branch))
    while branch**h < leaves:
        h += 1
    while h > 0 and branch ** (h - 1) >= leaves:
        h -= 1
    return Answer(value=h, display=str(h), comparable=h)


class BPlusTreeHeightGenerator(BaseGenerator):
    id = "bplus_height"
    version = 1
    title = "B+ tree height for N keys"
    node_id = "dbms.indexing.bplus_height"
    params = [ParamSpec(name="order", lo=3, hi=9), ParamSpec(name="keys", lo=5, hi=5000)]
    bucket = 3

    def sample_params(self, seed: int) -> dict[str, Any]:
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        return {"order": rng.randint(3, 9), "keys": rng.randint(5, 5000)}

    @property
    def solvers(self) -> tuple[Callable[..., Answer], Callable[..., Answer]]:
        return _height_iter, _height_bisect

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        stem = (
            f"A B+ tree of order {params['order']} stores {params['keys']} keys. "
            f"What is its height (leaf level = 0)?"
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
        order, keys = _nums(params)
        # Mistake: treat order as key capacity (off-by-one in fan-out).
        wrong = max(0, math.ceil(math.log(max(1, math.ceil(keys / max(1, order - 1))), max(2, order))))
        out: list[Distractor] = []
        if wrong != answer.comparable:
            out.append(
                Distractor(
                    value=wrong,
                    display=str(wrong),
                    error_tag="bplus_order_off_by_one",
                    rationale="Confused order (pointers) with key capacity (order-1).",
                )
            )
        return out
