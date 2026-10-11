"""Generator registry.

Generators register themselves so the Foundry can discover, verify and serve
them by id and by concept node.
"""

from __future__ import annotations

from collections.abc import Callable

from edgen.foundry.generator import Generator


class Foundry:
    """In-memory registry of generators, keyed by ``id@version``."""

    def __init__(self) -> None:
        self._by_key: dict[str, Generator] = {}
        self._by_node: dict[str, list[str]] = {}

    @staticmethod
    def key(gen: Generator) -> str:
        return f"{gen.id}@{gen.version}"

    def register(self, gen: Generator) -> Generator:
        k = self.key(gen)
        if k in self._by_key and self._by_key[k] is not gen:
            raise ValueError(f"duplicate generator key {k}")
        self._by_key[k] = gen
        self._by_node.setdefault(gen.node_id, [])
        if k not in self._by_node[gen.node_id]:
            self._by_node[gen.node_id].append(k)
        return gen

    def get(self, key: str) -> Generator:
        try:
            return self._by_key[key]
        except KeyError as exc:
            raise KeyError(f"unknown generator {key!r}") from exc

    def for_node(self, node_id: str) -> list[Generator]:
        return [self._by_key[k] for k in self._by_node.get(node_id, [])]

    def all(self) -> list[Generator]:
        return list(self._by_key.values())

    def __len__(self) -> int:
        return len(self._by_key)


def generator(gen: Generator) -> Callable[[], Generator]:
    """Decorator that returns a factory registering into a module-level foundry."""

    def _factory() -> Generator:
        return gen

    return _factory
