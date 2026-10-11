"""Core cache (SystemsDesign §5, architecture §6).

~90% of lesson tokens are shared across learners. The *core* is cached by
``track × node × lang × depth × style × core_version``; only a thin per-user
*delta* is computed on top. This is what makes "free" feasible.
"""

from __future__ import annotations

from typing import Protocol

from edgen.lesson.ir import LessonIR


class CoreCache(Protocol):
    def get(self, key: str) -> LessonIR | None: ...
    def put(self, lesson: LessonIR) -> None: ...
    def hit_rate(self) -> float: ...


class InMemoryCoreCache:
    """Reference implementation. Production uses Redis; the interface is identical."""

    def __init__(self) -> None:
        self._store: dict[str, LessonIR] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> LessonIR | None:
        lesson = self._store.get(key)
        if lesson is None:
            self._misses += 1
        else:
            self._hits += 1
        return lesson

    def put(self, lesson: LessonIR) -> None:
        self._store[lesson.cache_key] = lesson

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    def __len__(self) -> int:
        return len(self._store)
