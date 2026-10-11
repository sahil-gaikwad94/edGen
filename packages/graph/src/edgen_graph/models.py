"""Graph domain models — SystemsDesign §2."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from fnmatch import fnmatch
from typing import Any


@dataclass(frozen=True)
class Source:
    id: str
    kind: str = "syllabus_notes"
    license: str = "CC-BY-SA-4.0"
    url: str | None = None


@dataclass(frozen=True)
class Node:
    """A concept/skill/project node in the immutable graph."""

    id: str
    title: str
    kind: str  # concept | skill | project
    topic: str  # cluster id, used by the planner's interleaving rule
    subject: str
    prereqs: tuple[str, ...]
    est_minutes: int
    difficulty_prior: float  # doubles as BKT p_init for fresh learners
    generators: tuple[str, ...] = ()
    misconceptions: tuple[str, ...] = ()
    sources: tuple[Source, ...] = ()
    volatile: bool = False
    review_by: date | None = None
    graph_version: int = 0

    @property
    def cluster(self) -> str:
        """Planner cluster (no more than 2 consecutive items from one)."""
        return self.topic


def _compile_weights(rules: list[dict[str, Any]], node_ids: list[str]) -> dict[str, float]:
    """Compile fnmatch weight rules into explicit per-node weights.

    First match wins (rules ordered specific → general). A node matched by no
    rule gets 0 — so an upcoming lens that weights nothing honestly reports
    readiness as None instead of a fake number.
    """
    weights: dict[str, float] = {}
    for nid in node_ids:
        w = 0.0
        for rule in rules:
            if fnmatch(nid, rule["match"]):
                w = float(rule["weight"])
                break
        weights[nid] = w
    return weights


@dataclass
class Lens:
    """A lens = chosen subgraph + weights + goal type + milestones (IdeaBrief §5)."""

    id: str
    goal_type: str  # exam | role | mastery
    track: str
    title: str
    weights: dict[str, float] = field(default_factory=dict)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def weight_of(self, node_id: str) -> float:
        return self.weights.get(node_id, 0.0)

    @property
    def weighted_nodes(self) -> list[str]:
        return [n for n, w in self.weights.items() if w > 0]
