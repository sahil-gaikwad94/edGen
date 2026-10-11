"""Lesson IR, renderers, cache and cache-first personalization."""

from __future__ import annotations

import pytest

from edgen.content.loader import load_lessons
from edgen.lesson.cache import InMemoryCoreCache
from edgen.lesson.ir import Block, BlockType, LessonIR
from edgen.lesson.personalize import build_delta
from edgen.lesson.render import render_audio_script, render_chat_text, render_html
from edgen.trust import Trust, TrustBadge


def test_lesson_badge_is_the_weakest_block():
    lesson = LessonIR(
        lesson_id="x@v1",
        node_id="x",
        blocks=[
            Block(id="b1", type=BlockType.CLAIM, text="c", badge=TrustBadge.verified("g@1")),
            Block(id="b2", type=BlockType.INTUITION, text="i", badge=TrustBadge.model_generated()),
        ],
    )
    assert lesson.badge is Trust.MODEL


def test_fully_verified_lesson_stays_verified():
    lesson = LessonIR(
        lesson_id="x@v1",
        node_id="x",
        blocks=[Block(id="b1", type=BlockType.CLAIM, text="c", badge=TrustBadge.verified("g@1"))],
    )
    assert lesson.badge is Trust.VERIFIED


def test_cache_key_shape():
    lesson = LessonIR(lesson_id="x@v1", node_id="cs.os.x", depth="deep", style="s", core_version=3)
    assert lesson.cache_key == "core:cs.os.x:en:deep:s:3"


def test_render_html_contains_badges_and_receipts():
    lesson = load_lessons()[0]
    html = render_html(lesson)
    assert "VERIFIED" in html
    assert "SOURCED" in html
    assert "receipt" in html
    assert "data-block-id" in html


def test_render_audio_flags_model_blocks():
    lesson = LessonIR(
        lesson_id="x@v1",
        node_id="x",
        title="T",
        blocks=[
            Block(id="b1", type=BlockType.INTUITION, text="guess", badge=TrustBadge.model_generated()),
            Block(id="b2", type=BlockType.CLAIM, text="fact", badge=TrustBadge.verified("g@1")),
        ],
    )
    script = render_audio_script(lesson)
    assert "(unverified) guess" in script
    assert "(unverified) fact" not in script


def test_render_chat_labels_tiers():
    lesson = load_lessons()[0]
    text = render_chat_text(lesson)
    assert "[VERIFIED]" in text
    assert "[MODEL]" in text


def test_core_cache_hit_rate():
    cache = InMemoryCoreCache()
    lesson = load_lessons()[0]
    cache.put(lesson)
    assert cache.get(lesson.cache_key) is lesson
    cache.get("missing")
    assert cache.hit_rate() == pytest.approx(0.5)


def test_delta_is_model_tier_and_prepends():
    core = load_lessons()[0]
    personalized = build_delta(core, recurring_error_tag="closure_one_step")
    assert personalized.delta_of == core.lesson_id
    assert len(personalized.blocks) == len(core.blocks) + 1
    # The composite badge must drop to MODEL because the delta is unverified.
    assert personalized.badge is Trust.MODEL
    # Core blocks are untouched (immutability).
    assert core.blocks[0].id == personalized.blocks[1].id


def test_delta_noop_without_signals():
    core = load_lessons()[0]
    assert build_delta(core) is core
