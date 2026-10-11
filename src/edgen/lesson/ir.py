"""Lesson IR — a block graph that renders to many surfaces (architecture §6).

Block types: ``claim, intuition, example, counterexample, proof, viz, lab, check``.
One IR renders to web, audio script, slides, chat-app text and reel. Every block
carries a trust badge and, where relevant, a receipt.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from edgen.trust import Trust, TrustBadge, weakest


class BlockType(StrEnum):
    CLAIM = "claim"
    INTUITION = "intuition"
    EXAMPLE = "example"
    COUNTEREXAMPLE = "counterexample"
    PROOF = "proof"
    VIZ = "viz"
    LAB = "lab"
    CHECK = "check"


class Block(BaseModel):
    id: str
    type: BlockType
    text: str = ""
    badge: TrustBadge
    #: For example/check blocks: the Foundry generator that backs it.
    ref: str | None = None
    #: For viz blocks: a template name + JSON spec (rendered by prebuilt components).
    template: str | None = None
    spec: dict[str, Any] = Field(default_factory=dict)
    #: For lab blocks: the runtime (pyodide) and starter code.
    runtime: str | None = None
    starter: str | None = None


class LessonIR(BaseModel):
    lesson_id: str
    core_version: int = 1
    lang: str = "en"
    depth: str = "standard"
    style: str = "default"
    title: str = ""
    node_id: str = ""
    blocks: list[Block] = Field(default_factory=list)
    #: Delta patch metadata (per-user personalization), if any.
    delta_of: str | None = None

    @property
    def badge(self) -> Trust:
        """A lesson is only as trustworthy as its weakest block."""
        return weakest([b.badge for b in self.blocks])

    @property
    def cache_key(self) -> str:
        """Core cache key (architecture §6)."""
        return (
            f"core:{self.node_id}:{self.lang}:{self.depth}:{self.style}:{self.core_version}"
        )

    def factual_blocks(self) -> list[Block]:
        from edgen.trust import factual_claim_allowed

        return [b for b in self.blocks if factual_claim_allowed(b.badge)]
