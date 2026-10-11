"""Cache mapping: which cache line/set a block maps to (OS/COA).

Two independent solvers:
  * ``_direct_arith``: pure modular arithmetic.
  * ``_direct_loop``: simulate the wrap-around over the address range.
Reported quantity: the *set index* for a set-associative cache (1-way = direct
mapped). The mapping is verified, so it is badge-eligible.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from edgen.foundry.generator import Answer, BaseGenerator, Distractor, Instance, ParamSpec


def _nums(params: dict[str, Any]) -> tuple[int, int, int]:
    return params["block_size"], params["num_lines"], params["block_addr"]


def _direct_arith(params: dict[str, Any]) -> Answer:
    block_size, num_lines, block_addr = _nums(params)
    sets = num_lines
    idx = (block_addr // block_size) % sets
    return Answer(value=idx, display=str(idx), comparable=idx)


def _direct_loop(params: dict[str, Any]) -> Answer:
    block_size, num_lines, block_addr = _nums(params)
    # Simulate the mapping cycle without modular arithmetic.
    cycle = list(range(num_lines))
    pos = 0
    for _ in range(block_addr // block_size):
        pos = cycle[(cycle.index(pos) + 1) % len(cycle)]
    return Answer(value=pos, display=str(pos), comparable=pos)


class CacheMappingGenerator(BaseGenerator):
    id = "cache_mapping"
    version = 1
    title = "Set index for a set-associative cache"
    node_id = "cs.os.cache_mapping"
    params = [
        ParamSpec(name="block_size", lo=4, hi=64),
        ParamSpec(name="num_lines", lo=2, hi=16),
        ParamSpec(name="block_addr", lo=0, hi=4096),
    ]
    bucket = 2

    def sample_params(self, seed: int) -> dict[str, Any]:
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        block_size = rng.choice([4, 8, 16, 32, 64])
        num_lines = rng.choice([2, 4, 8, 16])
        block_addr = rng.randint(0, 4096)
        return {"block_size": block_size, "num_lines": num_lines, "block_addr": block_addr}

    @property
    def solvers(self) -> tuple[Callable[..., Answer], Callable[..., Answer]]:
        return _direct_arith, _direct_loop

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        stem = (
            f"A cache has block size {params['block_size']} B and {params['num_lines']} "
            f"lines (1-way). Which set index does block address {params['block_addr']} map to?"
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
        block_size, num_lines, block_addr = _nums(params)
        # Mistake: divide by lines instead of block size (byte/line confusion).
        wrong1 = (block_addr // num_lines) % num_lines
        # Mistake: forget the modulo (use the block number as the index).
        wrong2 = block_addr // block_size
        out: list[Distractor] = []
        seen = {answer.comparable}
        for v, tag, why in [
            (wrong1, "cache_byte_line_confusion", "Divided the address by lines, not block size."),
            (wrong2, "cache_no_modulo", "Used the block number directly, ignoring the set count."),
        ]:
            if v not in seen:
                seen.add(v)
                out.append(Distractor(value=v, display=str(v), error_tag=tag, rationale=why))
        return out
