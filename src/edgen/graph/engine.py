"""The Concept Graph engine: versioned graph, lens readiness, frontier.

Loaded in memory per process (≈2k nodes at launch). Readiness is computed on
demand from a mastery map: ``Σ w·m_eff / Σ w`` (SystemsDesign §2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from edgen.graph.model import ConceptNode, GraphVersion, Lens, NodeKind


class GraphError(ValueError):
    """Raised when a graph or lens is malformed."""


class ConceptGraph:
    """An immutable view over one :class:`GraphVersion`.

    Nodes are addressed by canonical id; lookups transparently resolve aliases so
    callers can pass historical ids that were merged away.
    """

    def __init__(self, version: GraphVersion) -> None:
        self._version = version
        self._nodes = version.nodes
        self._aliases = version.aliases
        self._validate()

    # -- construction ---------------------------------------------------------
    @property
    def version(self) -> int:
        return self._version.version

    @property
    def aliases(self) -> Mapping[str, str]:
        return self._aliases

    def _validate(self) -> None:
        for node in self._nodes.values():
            for pre in node.prereqs:
                canonical = self._version.resolve(pre)
                if canonical not in self._nodes:
                    raise GraphError(f"node {node.id!r} has unknown prereq {pre!r}")

    # -- lookup ---------------------------------------------------------------
    def __contains__(self, node_id: str) -> bool:
        return self.resolve(node_id) in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def resolve(self, node_id: str) -> str:
        return self._version.resolve(node_id)

    def get(self, node_id: str) -> ConceptNode:
        canonical = self.resolve(node_id)
        try:
            return self._nodes[canonical]
        except KeyError as exc:
            raise GraphError(f"unknown node {node_id!r}") from exc

    def nodes(self) -> Iterable[ConceptNode]:
        return self._nodes.values()

    def prereqs(self, node_id: str) -> list[str]:
        return [self.resolve(p) for p in self.get(node_id).prereqs]

    # -- traversal ------------------------------------------------------------
    def topological_order(self, node_ids: Iterable[str] | None = None) -> list[str]:
        """Return node ids in prerequisite order (stable, deterministic).

        Ties are broken by id so plans and tests are reproducible.
        """
        scope = {self.resolve(n) for n in node_ids} if node_ids is not None else set(self._nodes)
        indeg: dict[str, int] = dict.fromkeys(scope, 0)
        children: dict[str, list[str]] = {n: [] for n in scope}
        for n in scope:
            for pre in self.prereqs(n):
                if pre in scope:
                    indeg[n] += 1
                    children[pre].append(n)
        ready = sorted(n for n, d in indeg.items() if d == 0)
        order: list[str] = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for c in sorted(children[n]):
                indeg[c] -= 1
                if indeg[c] == 0:
                    ready.append(c)
                    ready.sort()
        if len(order) != len(scope):
            raise GraphError("cycle detected in concept graph")
        return order

    def prerequisites_met(
        self, node_id: str, mastery: Mapping[str, float], threshold: float = 0.7
    ) -> bool:
        """True if every direct prerequisite has effective mastery ≥ ``threshold``."""
        return all(mastery.get(p, 0.0) >= threshold for p in self.prereqs(node_id))

    # -- lens maths -----------------------------------------------------------
    def lens_node_ids(self, lens: Lens) -> list[str]:
        return [self.resolve(n) for n in lens.node_ids()]

    def readiness(self, lens: Lens, mastery: Mapping[str, float]) -> float:
        """Weighted readiness in [0, 1]: ``Σ w·m_eff / Σ w``.

        Missing nodes count as zero mastery. Weight-0 nodes are ignored.
        """
        weights = {self.resolve(k): v for k, v in lens.weights().items()}
        total_w = sum(w for w in weights.values() if w > 0)
        if total_w <= 0:
            return 0.0
        acc = sum(w * float(mastery.get(n, 0.0)) for n, w in weights.items() if w > 0)
        return max(0.0, min(1.0, acc / total_w))

    def frontier(
        self,
        lens: Lens,
        mastery: Mapping[str, float],
        *,
        low: float = 0.3,
        high: float = 0.7,
        prereq_threshold: float = 0.7,
    ) -> list[str]:
        """Nodes that are ready to learn: prereqs met, own mastery in [low, high).

        Only nodes inside the lens are returned, ordered by graph topology.
        """
        scope = set(self.lens_node_ids(lens))
        out: list[str] = []
        for n in self.topological_order(scope):
            m = float(mastery.get(n, 0.0))
            if low <= m < high and self.prerequisites_met(n, mastery, prereq_threshold):
                out.append(n)
        return out

    def prerequisite_closure(self, node_ids: Iterable[str]) -> list[str]:
        """All transitive prerequisites of the given nodes, in topological order."""
        seen: set[str] = set()
        stack = [self.resolve(n) for n in node_ids]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.prereqs(n))
        return self.topological_order(seen)

    def starters(self, lens: Lens, mastery: Mapping[str, float]) -> list[str]:
        """Nodes a learner can begin now: prereqs met and mastery still low.

        The documented frontier band (m_eff in [0.3, 0.7)) assumes a learner has
        history. A brand-new learner has m_eff = 0 on everything, so the planner
        also needs this cold-start set (prereqs met, m_eff < 0.7) to avoid an
        empty plan on day one.
        """
        scope = set(self.lens_node_ids(lens))
        return [
            n
            for n in self.topological_order(scope)
            if float(mastery.get(n, 0.0)) < 0.7 and self.prerequisites_met(n, mastery)
        ]

    def track_switch_credit(
        self, from_lens: Lens, to_lens: Lens, mastery: Mapping[str, float]
    ) -> dict[str, float]:
        """Report readiness before/after a switch.

        Mastery on shared nodes carries over untouched; nothing resets
        (SystemsDesign §2). Returns readiness under each lens plus the shared-node
        contribution, so the UI can say "you're already 41% ready".
        """
        return {
            "from_readiness": self.readiness(from_lens, mastery),
            "to_readiness": self.readiness(to_lens, mastery),
            "shared_nodes": float(len(set(self.lens_node_ids(from_lens)) & set(self.lens_node_ids(to_lens)))),
        }

    def nodes_by_kind(self, kind: NodeKind) -> list[ConceptNode]:
        return [n for n in self._nodes.values() if n.kind == kind]
