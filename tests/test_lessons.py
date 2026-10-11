"""Lesson IR: badges, receipts, cache keys, renderers, deltas (architecture §6)."""
from pathlib import Path

import pytest

from edgen_lesson_ir import (
    Block,
    LessonCore,
    ReceiptError,
    apply_delta,
    cache_key,
    lesson_to_html,
    load_lesson,
    load_sources,
    validate_receipts,
)

ROOT = Path(__file__).resolve().parents[1]
LESSONS = sorted((ROOT / "content" / "lessons").glob("*.json"))


@pytest.fixture(scope="module")
def sources():
    return load_sources(ROOT / "content")


def test_all_authored_lessons_load_and_ground_receipts(sources):
    assert len(LESSONS) >= 9
    for f in LESSONS:
        lesson = load_lesson(f, sources)  # raises if a SOURCED quote is ungrounded
        assert lesson.blocks
        for b in lesson.blocks:
            if b.badge == "SOURCED":
                assert b.receipt and b.receipt.kind == "source_span"
                assert b.receipt.span and b.receipt.span[1] > b.receipt.span[0]
                assert b.receipt.license


def test_model_blocks_cannot_carry_source_receipts(sources):
    bad = LessonCore(
        lesson_id="x@v1", node_id="dbms.er.entity", title="t",
        blocks=[Block(id="b1", type="claim", badge="MODEL", text="hi",
                      receipt={"kind": "source_span", "source_id": "edgen_syllabus_notes", "quote": "anything"})],
    )
    with pytest.raises(ReceiptError):
        validate_receipts(bad, sources)


def test_ungrounded_quote_rejected(sources):
    bad = LessonCore(
        lesson_id="x@v1", node_id="dbms.er.entity", title="t",
        blocks=[Block(id="b1", type="claim", badge="SOURCED", text="claim",
                      receipt={"kind": "source_span", "source_id": "edgen_syllabus_notes",
                               "quote": "this quote does not exist anywhere"})],
    )
    with pytest.raises(ReceiptError, match="quote not found"):
        validate_receipts(bad, sources)


def test_cache_key_format():
    assert cache_key("os", "os.scheduling.rr", "en", "standard", "default", 3) == \
        "core:os:os.scheduling.rr:en:standard:default:3"


def test_html_renderer_badges(sources):
    lesson = load_lesson(ROOT / "content" / "lessons/os.scheduling.rr.json", sources)
    html = lesson_to_html(lesson)
    assert "lg-badge-sourced" in html
    assert "lg-badge-verified" in html
    assert "6.67" in html


def test_json_patch_delta(sources):
    lesson = load_lesson(ROOT / "content/lessons/dbms.stor.pages.json", sources)
    patched = apply_delta(lesson, [
        {"op": "add", "path": "/blocks/1", "value": {"id": "x", "type": "claim", "badge": "MODEL", "text": "delta!"}},
        {"op": "replace", "path": "/blocks/0/text", "value": "rewritten"},
    ])
    assert len(patched.blocks) == len(lesson.blocks) + 1
    assert patched.blocks[0].text == "rewritten"
    # original untouched (immutability of cached core)
    assert lesson.blocks[0].text != "rewritten"
