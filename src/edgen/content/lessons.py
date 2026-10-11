"""Lesson cores — shared, cached, reviewable (SystemsDesign §5).

These are the seed cores for W0. They demonstrate the trust model end to end:
a SOURCED claim, VERIFIED examples backed by Foundry generators, a MODEL intuition
block, a viz template, and a check. Every block carries a badge + receipt.
"""

from __future__ import annotations

from edgen.lesson.ir import Block, BlockType, LessonIR
from edgen.trust import TrustBadge


def _closure_lesson() -> LessonIR:
    return LessonIR(
        lesson_id="cs.dbms.normalization.fd_closure@v1",
        node_id="cs.dbms.normalization.fd_closure",
        title="Attribute closure",
        depth="standard",
        blocks=[
            Block(
                id="b1",
                type=BlockType.CLAIM,
                text=(
                    "The attribute closure X+ of a set of attributes X under a set "
                    "of functional dependencies F is the set of all attributes that "
                    "can be functionally determined by X."
                ),
                badge=TrustBadge.sourced("gate-syllabus-2027", (0, 60), "official-syllabus"),
            ),
            Block(
                id="b2",
                type=BlockType.INTUITION,
                text=(
                    "Think of FDs as one-way streets. Starting from X, walk every "
                    "street whose start is already reachable. Repeat until nothing new "
                    "is reachable. What you can reach is X+."
                ),
                badge=TrustBadge.model_generated(kind="intuition"),
            ),
            Block(
                id="b3",
                type=BlockType.PROOF,
                text=(
                    "Fixpoint algorithm: R <- X; while some FD L->R has L subset of R "
                    "and R not subset of R, set R <- R union R. Terminates because the "
                    "attribute set is finite and monotonically grows; the result is the "
                    "least fixpoint, hence exactly X+."
                ),
                badge=TrustBadge.tested("proof:closure-fixpoint"),
            ),
            Block(
                id="b4",
                type=BlockType.EXAMPLE,
                text="Compute (A)+ for R(A,B,C,D) with A->BC, BC->D, D->C.",
                ref="fd_closure@1",
                badge=TrustBadge.verified("fd_closure@1", seeds_checked=5000),
            ),
            Block(
                id="b5",
                type=BlockType.VIZ,
                text="Watch the closure grow, one derivation at a time.",
                template="fd_graph",
                spec={"highlight": "closure"},
                badge=TrustBadge.model_generated(kind="viz_spec"),
            ),
            Block(
                id="b6",
                type=BlockType.CHECK,
                text="Try a fresh instance. The answer is computed by verified code.",
                ref="fd_closure@1",
                badge=TrustBadge.verified("fd_closure@1", seeds_checked=5000),
            ),
        ],
    )


def _cache_lesson() -> LessonIR:
    return LessonIR(
        lesson_id="cs.os.cache_mapping@v1",
        node_id="cs.os.cache_mapping",
        title="Cache mapping: which set?",
        depth="standard",
        blocks=[
            Block(
                id="b1",
                type=BlockType.CLAIM,
                text=(
                    "In a set-associative cache, block address b maps to set "
                    "(b / block_size) mod num_sets."
                ),
                badge=TrustBadge.sourced("coa-text", (100, 160), "cc-by"),
            ),
            Block(
                id="b2",
                type=BlockType.INTUITION,
                text=(
                    "The block number is the address divided by block size. The set is "
                    "that block number wrapped around the number of sets."
                ),
                badge=TrustBadge.model_generated(kind="intuition"),
            ),
            Block(
                id="b3",
                type=BlockType.COUNTEREXAMPLE,
                text=(
                    "Dividing the address by the number of lines (not block size) is a "
                    "common slip; it mixes up bytes-per-block with number-of-sets."
                ),
                badge=TrustBadge.model_generated(kind="misconception"),
            ),
            Block(
                id="b4",
                type=BlockType.EXAMPLE,
                text="A 1-way cache: block size 16 B, 16 lines, address 3615. Which set?",
                ref="cache_mapping@1",
                badge=TrustBadge.verified("cache_mapping@1", seeds_checked=5000),
            ),
            Block(
                id="b5",
                type=BlockType.CHECK,
                text="Solve a fresh mapping.",
                ref="cache_mapping@1",
                badge=TrustBadge.verified("cache_mapping@1", seeds_checked=5000),
            ),
        ],
    )


def _page_replacement_lesson() -> LessonIR:
    return LessonIR(
        lesson_id="cs.os.page_replacement@v1",
        node_id="cs.os.page_replacement",
        title="FIFO page replacement",
        depth="standard",
        blocks=[
            Block(
                id="b1",
                type=BlockType.CLAIM,
                text=(
                    "FIFO evicts the page that has been in memory the longest, "
                    "regardless of use."
                ),
                badge=TrustBadge.sourced("os-text", (200, 240), "cc-by-sa"),
            ),
            Block(
                id="b2",
                type=BlockType.INTUITION,
                text=(
                    "Keep the frames in arrival order. A new page takes the oldest "
                    "frame; a hit changes nothing about that order."
                ),
                badge=TrustBadge.model_generated(kind="intuition"),
            ),
            Block(
                id="b3",
                type=BlockType.EXAMPLE,
                text="3 frames, reference 0 0 2 1 1 2 0. Count the faults.",
                ref="page_replacement_fifo@1",
                badge=TrustBadge.verified("page_replacement_fifo@1", seeds_checked=5000),
            ),
            Block(
                id="b4",
                type=BlockType.CHECK,
                text="Fresh reference string, FIFO fault count.",
                ref="page_replacement_fifo@1",
                badge=TrustBadge.verified("page_replacement_fifo@1", seeds_checked=5000),
            ),
        ],
    )


def lesson_cores() -> list[LessonIR]:
    return [_closure_lesson(), _cache_lesson(), _page_replacement_lesson()]
