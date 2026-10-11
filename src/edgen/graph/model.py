"""Data model for the Concept Graph and lenses (architecture §4)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class NodeKind(StrEnum):
    CONCEPT = "concept"
    SKILL = "skill"
    PROJECT = "project"


class GoalType(StrEnum):
    EXAM = "exam"
    ROLE = "role"
    MASTERY = "mastery"


class ConceptNode(BaseModel):
    """A node in the Concept Graph.

    ``id`` is a dotted path such as ``cs.os.scheduling`` or ``ml.optim.adam``.
    ``prereqs`` reference other node ids. ``generators`` name Foundry generators
    that can produce verified practice for this node.
    """

    id: str
    title: str
    kind: NodeKind = NodeKind.CONCEPT
    prereqs: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    difficulty_prior: float = 0.5
    #: Estimated minutes by depth, e.g. {"intro": 8, "standard": 14, "deep": 30}.
    est_minutes: dict[str, int] = Field(default_factory=dict)
    generators: list[str] = Field(default_factory=list)
    volatile: bool = False
    review_by: dt.date | None = None
    reviewer: str | None = None

    @field_validator("id")
    @classmethod
    def _dotted(cls, v: str) -> str:
        if not v or any(part == "" for part in v.split(".")):
            raise ValueError(f"node id must be a non-empty dotted path, got {v!r}")
        return v

    @field_validator("difficulty_prior")
    @classmethod
    def _unit(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("difficulty_prior must be in [0, 1]")
        return v


class LensNode(BaseModel):
    lens_id: str
    node_id: str
    #: Weight of this node for the lens objective (exam marks or role readiness).
    weight: float = 1.0
    #: Ordering hint for authoring/teaching sequence.
    ord: int = 0


class Lens(BaseModel):
    """A track is a lens over the shared Concept Graph."""

    id: str
    title: str
    goal_type: GoalType
    nodes: list[LensNode] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    mock_config: dict = Field(default_factory=dict)
    #: Optional exam date for exam lenses (drives the planner objective).
    exam_date: dt.date | None = None

    def weights(self) -> dict[str, float]:
        return {ln.node_id: ln.weight for ln in self.nodes}

    def node_ids(self) -> list[str]:
        return [ln.node_id for ln in self.nodes]


class GraphVersion(BaseModel):
    """A published, immutable graph version."""

    version: int
    created_at: dt.datetime
    nodes: dict[str, ConceptNode]
    #: old_id -> new_id, so Twin history survives merges/renames.
    aliases: dict[str, str] = Field(default_factory=dict)
    note: str = ""

    def resolve(self, node_id: str) -> str:
        """Follow the alias chain to the canonical node id."""
        seen: set[str] = set()
        cur = node_id
        while cur in self.aliases:
            if cur in seen:
                raise ValueError(f"alias cycle at {cur!r}")
            seen.add(cur)
            cur = self.aliases[cur]
        return cur
