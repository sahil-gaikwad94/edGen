"""Lesson IR + renderers + cache (SystemsDesign §5, architecture §6)."""

from edgen.lesson.cache import CoreCache, InMemoryCoreCache
from edgen.lesson.ir import Block, BlockType, LessonIR
from edgen.lesson.personalize import apply_delta, build_delta
from edgen.lesson.render import (
    render_audio_script,
    render_block_html,
    render_chat_text,
    render_html,
)

__all__ = [
    "Block",
    "BlockType",
    "LessonIR",
    "render_audio_script",
    "render_block_html",
    "render_chat_text",
    "render_html",
    "CoreCache",
    "InMemoryCoreCache",
    "apply_delta",
    "build_delta",
]
