"""In-memory application state: graph, lens, foundry, pools, lessons, twins.

Everything the API needs is wired here so the service is runnable with no
external dependencies. Swap the dicts for Postgres/Redis in production; the
call sites do not change.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

from edgen.content.loader import build_graph_v0, load_gate_cse_lens, load_lessons
from edgen.foundry.generators.catalog import load_generators, verification_reports
from edgen.foundry.pool import InstancePool, PoolConfig
from edgen.foundry.registry import Foundry
from edgen.graph.engine import ConceptGraph
from edgen.graph.model import Lens
from edgen.lesson.cache import InMemoryCoreCache
from edgen.lesson.ir import LessonIR
from edgen.twin.service import Attempt, Twin


class AppState:
    """Holds all in-process state for one API instance."""

    def __init__(self, *, pool_per_bucket: int = 25, verify_seeds: int = 2000) -> None:
        self.graph: ConceptGraph = build_graph_v0()
        self.lens: Lens = load_gate_cse_lens()
        self.foundry: Foundry = load_generators(seeds=verify_seeds)
        self._reports = {r.generator_id: r for r in verification_reports(seeds=verify_seeds)}
        self.pool_config = PoolConfig(per_bucket=pool_per_bucket)
        self._pools: dict[str, InstancePool] = {}
        self.core_cache = InMemoryCoreCache()
        self.twins: dict[str, Twin] = {}
        self._attempt_log: list[Attempt] = []
        self._seen_attempt_ids: set[str] = set()
        for lesson in load_lessons():
            self.core_cache.put(lesson)
        # Seed a demo learner so the API is usable out of the box.
        self.get_twin("demo")

    # -- twins ----------------------------------------------------------------
    def get_twin(self, user_id: str) -> Twin:
        twin = self.twins.get(user_id)
        if twin is None:
            twin = Twin(user_id)
            self.twins[user_id] = twin
        return twin

    # -- pools ----------------------------------------------------------------
    def pool_for_node(self, node_id: str) -> tuple[InstancePool, list[str]] | None:
        """Return a pool and its generator keys for a node, or None if unbacked."""
        gens = self.foundry.for_node(node_id)
        if not gens:
            return None
        # One pool per node, built from the first generator for that node.
        key = gens[0].id
        pool = self._pools.get(key)
        if pool is None:
            pool = InstancePool(gens[0], self.pool_config)
            self._pools[key] = pool
        return pool, [f"{g.id}@{g.version}" for g in gens]

    # -- attempts -------------------------------------------------------------
    def record_attempt(self, attempt: Attempt) -> bool:
        """Append to the log and fold into the Twin. Returns False if duplicate."""
        if attempt.id in self._seen_attempt_ids:
            return False
        self._seen_attempt_ids.add(attempt.id)
        self._attempt_log.append(attempt)
        self.get_twin(attempt.user_id).apply(attempt)
        return True

    def attempts(self, user_id: str | None = None) -> list[Attempt]:
        if user_id is None:
            return list(self._attempt_log)
        return [a for a in self._attempt_log if a.user_id == user_id]

    def export_user(self, user_id: str) -> dict:
        twin = self.get_twin(user_id)
        return {
            "user_id": user_id,
            "attempts": [a.__dict__ for a in self.attempts(user_id)],
            "error_genome": twin.error_genome(),
            "mastery": {
                n: {
                    "p_known": st.p_known,
                    "stability_days": st.stability_days,
                    "attempts": st.attempts,
                }
                for n, st in twin._states.items()  # noqa: SLF001
            },
        }

    def delete_user(self, user_id: str) -> None:
        self.twins.pop(user_id, None)
        self._attempt_log = [a for a in self._attempt_log if a.user_id != user_id]

    # -- verification receipts (admin) ----------------------------------------
    def verification_receipts(self) -> list[dict]:
        return [
            {
                "generator_id": r.generator_id,
                "version": r.version,
                "ok": r.ok,
                "seeds_checked": r.seeds_checked,
                "agreements": r.agreements,
                "disagreements": len(r.disagreements),
            }
            for r in self._reports.values()
        ]

    def lesson_for(self, node_id: str) -> LessonIR | None:
        for lesson in self.core_cache._store.values():  # noqa: SLF001
            if lesson.node_id == node_id:
                return lesson
        return None


@lru_cache(maxsize=1)
def get_state() -> AppState:
    return AppState()


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
