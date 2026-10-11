"""ConceptGraph: loading, validation, readiness, frontier (SystemsDesign §2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

import yaml

from .models import Lens, Node, Source, _compile_weights


class GraphValidationError(Exception):
    """Raised when a graph version fails the automated authoring checks."""


@dataclass
class ContentBundle:
    """Everything loaded from the content directory."""

    graph: "ConceptGraph"
    lenses: dict[str, Lens]
    tracks: dict[str, dict]
    content_dir: Path


class ConceptGraph:
    """Immutable, versioned concept graph held in memory (~2k nodes at scale)."""

    def __init__(self, version: int, nodes: Iterable[Node], aliases: dict[str, str] | None = None):
        self.version = version
        self.nodes: dict[str, Node] = {n.id: n for n in nodes}
        self.aliases: dict[str, str] = aliases or {}
        self.validate()

    # -- identity / lookup -------------------------------------------------
    def resolve(self, node_id: str) -> str:
        seen = set()
        cur = node_id
        while cur in self.aliases and cur not in seen:
            seen.add(cur)
            cur = self.aliases[cur]
        return cur

    def get(self, node_id: str) -> Node:
        return self.nodes[self.resolve(node_id)]

    def __contains__(self, node_id: str) -> bool:
        return self.resolve(node_id) in self.nodes

    # -- validation (authoring pipeline, SystemsDesign §2.3) ---------------
    def validate(self) -> None:
        if not self.nodes:
            raise GraphValidationError("graph has no nodes")
        for n in self.nodes.values():
            for p in n.prereqs:
                if p not in self.nodes:
                    raise GraphValidationError(f"{n.id}: unknown prereq {p}")
            if not (0.0 <= n.difficulty_prior <= 1.0):
                raise GraphValidationError(f"{n.id}: difficulty_prior out of range")
        # acyclicity via iterative DFS
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self.nodes}
        for start in self.nodes:
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            path: list[str] = []
            while stack:
                nid, pi = stack[-1]
                if color[nid] == WHITE:
                    color[nid] = GRAY
                    path.append(nid)
                pr = self.nodes[nid].prereqs
                advanced = False
                while pi < len(pr):
                    nxt = pr[pi]
                    pi += 1
                    if color[nxt] == GRAY:
                        cycle = path[path.index(nxt):] + [nxt]
                        raise GraphValidationError("cycle: " + " -> ".join(cycle))
                    if color[nxt] == WHITE:
                        stack[-1] = (nid, pi)
                        stack.append((nxt, 0))
                        advanced = True
                        break
                if not advanced:
                    color[nid] = BLACK
                    path.pop()
                    stack.pop()

    # -- orders ------------------------------------------------------------
    def topo_order(self) -> list[str]:
        """Prereqs-before-dependents ordering (Kahn)."""
        indeg = {nid: 0 for nid in self.nodes}
        for n in self.nodes.values():
            for _ in n.prereqs:
                indeg[n.id] += 1  # edges prereq -> node
        dependents: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for n in self.nodes.values():
            for p in n.prereqs:
                dependents[p].append(n.id)
        queue = sorted(nid for nid, d in indeg.items() if d == 0)
        out: list[str] = []
        while queue:
            nid = queue.pop(0)
            out.append(nid)
            for dep in dependents[nid]:
                indeg[dep] -= 1
                if indeg[dep] == 0:
                    queue.append(dep)
            queue.sort()
        if len(out) != len(self.nodes):
            raise GraphValidationError("topo_order failed (cycle?)")
        return out

    def ancestors(self, node_id: str) -> set[str]:
        out: set[str] = set()
        stack = list(self.get(node_id).prereqs)
        while stack:
            nid = stack.pop()
            if nid in out:
                continue
            out.add(nid)
            stack.extend(self.get(nid).prereqs)
        return out

    # -- mastery-space queries --------------------------------------------
    def mastery_fn_valid(self, m: Callable[[str], float]) -> Callable[[str], float]:
        def safe(nid: str) -> float:
            v = m(nid)
            return min(1.0, max(0.0, float(v)))

        return safe

    def readiness(self, lens: Lens, m_eff: Callable[[str], float]) -> float | None:
        """lens_readiness = Σ w·m_eff / Σ w over nodes in this graph."""
        f = self.mastery_fn_valid(m_eff)
        num = den = 0.0
        for nid, w in lens.weights.items():
            if nid not in self.nodes or w <= 0:
                continue
            num += w * f(nid)
            den += w
        if den == 0:
            return None  # upcoming track: honest null, never a fake 0%
        return num / den

    def frontier(
        self,
        m_eff: Callable[[str], float],
        lo: float = 0.3,
        hi: float = 0.7,
        prereq_thr: float = 0.7,
    ) -> list[str]:
        """Nodes whose prereqs have m_eff ≥ 0.7 and own m_eff ∈ [lo, hi]."""
        f = self.mastery_fn_valid(m_eff)
        out = []
        for nid, n in self.nodes.items():
            if not (lo <= f(nid) <= hi):
                continue
            if all(f(p) >= prereq_thr for p in n.prereqs):
                out.append(nid)
        return sorted(out)

    def remediation(
        self,
        m_eff: Callable[[str], float],
        hi: float = 0.3,
        prereq_thr: float = 0.7,
    ) -> list[str]:
        """Prereqs met but mastery stuck below `hi` — needs a fresh path in.

        (Extension over the literal spec: without this, a node that drops
        below 0.3 after a bad diagnostic would become unreachable forever.)
        """
        f = self.mastery_fn_valid(m_eff)
        return sorted(
            nid
            for nid, n in self.nodes.items()
            if f(nid) < hi and all(f(p) >= prereq_thr for p in n.prereqs)
        )

    def learnable(self, m_eff: Callable[[str], float], prereq_thr: float = 0.7) -> list[str]:
        """Frontier ∪ remediation: everything a planner may teach right now."""
        return sorted(set(self.frontier(m_eff)) | set(self.remediation(m_eff, prereq_thr=prereq_thr)))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _node_from_dict(raw: dict, defaults: dict, graph_version: int, subject: str) -> Node:
    srcs = tuple(
        Source(id=s["id"], kind=s.get("kind", "syllabus_notes"), license=s.get("license", "CC-BY-SA-4.0"), url=s.get("url"))
        for s in (raw.get("sources") or defaults.get("sources") or [])
    )
    review_by = raw.get("review_by")
    return Node(
        id=raw["id"],
        title=raw["title"],
        kind=raw.get("kind", "concept"),
        topic=raw.get("topic") or raw["id"].rsplit(".", 1)[0],
        subject=raw.get("subject", subject),
        prereqs=tuple(raw.get("prereqs", [])),
        est_minutes=int(raw.get("est_minutes", raw.get("est", 10))),
        difficulty_prior=float(raw.get("difficulty_prior", raw.get("prior", 0.5))),
        generators=tuple(raw.get("generators", [])),
        misconceptions=tuple(raw.get("misconceptions", [])),
        sources=srcs,
        volatile=bool(raw.get("volatile", False)),
        review_by=date.fromisoformat(review_by) if review_by else None,
        graph_version=graph_version,
    )


def load_graph(graph_dir: Path) -> ConceptGraph:
    """Load and validate an immutable graph version from a directory of YAML files."""
    files = sorted(graph_dir.glob("*.yaml"))
    if not files:
        raise GraphValidationError(f"no graph files in {graph_dir}")
    nodes: list[Node] = []
    version: int | None = None
    for f in files:
        data = yaml.safe_load(f.read_text())
        version = data.get("graph_version", version)
        defaults = {"sources": data.get("default_sources", [])}
        subject = data.get("subject", "")
        for raw in data.get("nodes", []):
            nodes.append(_node_from_dict(raw, defaults, int(version or 0), subject))
    aliases_file = graph_dir / "aliases.yaml"
    aliases: dict[str, str] = {}
    if aliases_file.exists():
        aliases = {a["old"]: a["new"] for a in yaml.safe_load(aliases_file.read_text())}
    return ConceptGraph(version=int(version or 0), nodes=nodes, aliases=aliases)


def load_lenses(path: Path, graph: ConceptGraph) -> dict[str, Lens]:
    data = yaml.safe_load(path.read_text())
    out: dict[str, Lens] = {}
    for raw in data.get("lenses", []):
        weights = _compile_weights(raw.get("weight_rules", []), list(graph.nodes))
        out[raw["id"]] = Lens(
            id=raw["id"],
            goal_type=raw["goal_type"],
            track=raw.get("track", raw["id"]),
            title=raw.get("title", raw["id"]),
            weights=weights,
            milestones=list(raw.get("milestones", [])),
            config=dict(raw.get("config", {})),
        )
    return out


def load_tracks(path: Path) -> dict[str, dict]:
    data = yaml.safe_load(path.read_text())
    return {t["id"]: t for t in data.get("tracks", [])}


def load_content(content_dir: Path | str) -> ContentBundle:
    content_dir = Path(content_dir)
    graph = load_graph(content_dir / "graph" / "v0")
    lenses = load_lenses(content_dir / "lenses.yaml", graph)
    tracks = load_tracks(content_dir / "tracks.yaml")
    return ContentBundle(graph=graph, lenses=lenses, tracks=tracks, content_dir=content_dir)
