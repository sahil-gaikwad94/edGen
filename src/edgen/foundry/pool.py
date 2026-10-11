"""Instance pools (SystemsDesign §6, architecture §18).

Problems are pre-generated into pools so serving is ≤ 300 ms with no model in the
loop. Each instance stores its params; the answer key is recomputed on demand by
the verified solver (never shipped to the client).
"""

from __future__ import annotations

from pydantic import BaseModel

from edgen.foundry.generator import Answer, Distractor, Generator, Instance


class PoolConfig(BaseModel):
    #: How many instances to pre-generate per difficulty bucket.
    per_bucket: int = 2000
    buckets: tuple[int, ...] = (0, 1, 2, 3, 4)


class InstancePool:
    """A pre-generated pool for one generator version.

    Seeds are namespaced per bucket so buckets are disjoint and reproducible.
    """

    def __init__(self, gen: Generator, config: PoolConfig | None = None) -> None:
        self.gen = gen
        self.config = config or PoolConfig()
        self._instances: dict[str, Instance] = {}
        self._by_bucket: dict[int, list[str]] = {b: [] for b in self.config.buckets}
        self._build()

    def _build(self) -> None:
        for bucket in self.config.buckets:
            for i in range(self.config.per_bucket):
                seed = bucket * 1_000_000 + i
                inst = self.gen.instance(seed)
                inst.bucket = bucket
                iid = inst.instance_id
                self._instances[iid] = inst
                self._by_bucket[bucket].append(iid)

    def __len__(self) -> int:
        return len(self._instances)

    def get(self, instance_id: str) -> Instance:
        return self._instances[instance_id]

    def bucket(self, bucket: int) -> list[Instance]:
        return [self._instances[i] for i in self._by_bucket.get(bucket, [])]

    def answer_key(self, instance_id: str) -> tuple[Answer, list[Distractor]]:
        """Server-side answer key. Never send this to the client."""
        inst = self.get(instance_id)
        answer = self.gen.solvers[0](inst.params)
        return answer, self.gen.distractors(inst.params, answer)

    def options(self, instance_id: str) -> list[dict]:
        """Client-safe options: correct answer + distractors, shuffled deterministically."""
        answer, distractors = self.answer_key(instance_id)
        import random

        rng = random.Random(f"opts:{instance_id}")
        opts = [{"display": answer.display, "correct": True, "error_tag": None}]
        for d in distractors:
            opts.append({"display": d.display, "correct": False, "error_tag": d.error_tag})
        rng.shuffle(opts)
        return opts

    def grade(self, instance_id: str, comparable: object) -> dict:
        """Grade a submission against the verified key."""
        answer, distractors = self.answer_key(instance_id)
        correct = comparable == (answer.comparable if answer.comparable is not None else answer.value)
        tag = None
        if not correct:
            for d in distractors:
                if comparable == d.value:
                    tag = d.error_tag
                    break
        return {"correct": correct, "error_tag": tag, "answer": answer.display}
