"""Cache-first personalization: the per-user *delta* over a shared core.

The core is shared and cached; the delta is a small, cheap patch that adds a
personal analogy, a prerequisite refresher, or a nod to the learner's recurring
mistake. Deltas are MODEL-tier (generated, unverified) and never introduce factual
claims — facts live in the verified/sourced core.

In Phase 1 the delta is assembled deterministically from Twin signals (error
genome, frontier), so it needs no model call at all. The ``build_delta`` seam is
where a T0/T1 model would plug in later.
"""

from __future__ import annotations

from edgen.lesson.ir import Block, BlockType, LessonIR
from edgen.trust import TrustBadge


def build_delta(
    core: LessonIR,
    *,
    recurring_error_tag: str | None = None,
    prerequisite_refresher: str | None = None,
    analogy: str | None = None,
) -> LessonIR:
    """Build a personalized lesson = core blocks + a thin MODEL-tier delta.

    The delta is appended as ``intuition`` blocks flagged MODEL, so the composite
    badge stays honest (a lesson is only as strong as its weakest block).
    """
    delta_blocks: list[Block] = []
    if prerequisite_refresher:
        delta_blocks.append(
            Block(
                id="delta-refresh",
                type=BlockType.INTUITION,
                text=f"Quick refresher before we start: {prerequisite_refresher}",
                badge=TrustBadge.model_generated(kind="prerequisite_refresher"),
            )
        )
    if recurring_error_tag:
        delta_blocks.append(
            Block(
                id="delta-mistake",
                type=BlockType.COUNTEREXAMPLE,
                text=(
                    "You've hit this before: "
                    f"{recurring_error_tag.replace('_', ' ')}. Watch for it here."
                ),
                badge=TrustBadge.model_generated(kind="error_nudge"),
            )
        )
    if analogy:
        delta_blocks.append(
            Block(
                id="delta-analogy",
                type=BlockType.INTUITION,
                text=analogy,
                badge=TrustBadge.model_generated(kind="analogy"),
            )
        )
    if not delta_blocks:
        return core
    return core.model_copy(
        update={
            "blocks": delta_blocks + core.blocks,
            "delta_of": core.lesson_id,
        }
    )


def apply_delta(core: LessonIR, delta_blocks: list[Block]) -> LessonIR:
    """Apply pre-built delta blocks to a cached core (keeps the core immutable)."""
    return core.model_copy(
        update={"blocks": list(delta_blocks) + core.blocks, "delta_of": core.lesson_id}
    )
