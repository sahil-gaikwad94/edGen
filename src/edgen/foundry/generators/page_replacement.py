"""FIFO page replacement: number of page faults for a reference string (OS).

Two independent solvers:
  * ``_fifo_deque``: a deque with a membership set.
  * ``_fifo_clock``: a circular buffer plus a hand-clock, simulating frame reuse.
Agreement across seeds is the trust signal.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Callable
from typing import Any

from edgen.foundry.generator import Answer, BaseGenerator, Distractor, Instance, ParamSpec


def _nums(params: dict[str, Any]) -> tuple[int, list[int]]:
    return params["frames"], params["ref"]


def _fifo_deque(params: dict[str, Any]) -> Answer:
    frames, ref = _nums(params)
    q: deque[int] = deque()
    present: set[int] = set()
    faults = 0
    for page in ref:
        if page not in present:
            faults += 1
            if len(q) == frames:
                old = q.popleft()
                present.discard(old)
            q.append(page)
            present.add(page)
    return Answer(value=faults, display=str(faults), comparable=faults)


def _fifo_clock(params: dict[str, Any]) -> Answer:
    frames, ref = _nums(params)
    ring: list[int | None] = [None] * frames
    hand = 0
    faults = 0
    for page in ref:
        if page in ring:
            continue
        faults += 1
        ring[hand] = page
        hand = (hand + 1) % frames
    return Answer(value=faults, display=str(faults), comparable=faults)


class FIFOPageReplacementGenerator(BaseGenerator):
    id = "page_replacement_fifo"
    version = 1
    title = "FIFO page replacement: fault count"
    node_id = "cs.os.page_replacement"
    params = [ParamSpec(name="frames", lo=2, hi=5), ParamSpec(name="ref_len", lo=6, hi=16)]
    bucket = 2

    def sample_params(self, seed: int) -> dict[str, Any]:
        rng = random.Random(f"{self.id}@{self.version}:{seed}")
        frames = rng.randint(2, 5)
        n_pages = rng.randint(3, 6)
        ref = [rng.randint(0, n_pages - 1) for _ in range(rng.randint(6, 16))]
        return {"frames": frames, "ref": ref}

    @property
    def solvers(self) -> tuple[Callable[..., Answer], Callable[..., Answer]]:
        return _fifo_deque, _fifo_clock

    def build(self, seed: int, params: dict[str, Any]) -> Instance:
        stem = (
            f"{params['frames']} frames, reference string "
            f"{' '.join(map(str, params['ref']))}. Number of page faults with FIFO?"
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
        frames, ref = _nums(params)
        # Mistake: count all references (assume every access faults).
        all_faults = len(ref)
        # Mistake: count distinct pages (assume no eviction ever).
        distinct = len(set(ref))
        out: list[Distractor] = []
        seen = {answer.comparable}
        for v, tag, why in [
            (all_faults, "page_count_all_refs", "Counted every reference as a fault."),
            (distinct, "page_count_distinct", "Counted distinct pages; ignored capacity evictions."),
        ]:
            if v not in seen:
                seen.add(v)
                out.append(Distractor(value=v, display=str(v), error_tag=tag, rationale=why))
        return out
