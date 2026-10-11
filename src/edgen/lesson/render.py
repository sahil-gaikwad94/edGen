"""Renderers — one Lesson IR, many surfaces (architecture §3, §6).

The web renderer emits semantic HTML with a trust badge and receipt on every
block. Audio/slides/chat renderers are thin projections of the same IR; adding a
surface never means re-authoring content.
"""

from __future__ import annotations

import html

from edgen.lesson.ir import Block, BlockType, LessonIR
from edgen.trust import Trust

_BADGE_CLASS = {
    Trust.VERIFIED: "badge badge-verified",
    Trust.SOURCED: "badge badge-sourced",
    Trust.JUDGED: "badge badge-judged",
    Trust.MODEL: "badge badge-model",
}

_BLOCK_CLASS = {
    BlockType.CLAIM: "block block-claim",
    BlockType.INTUITION: "block block-intuition",
    BlockType.EXAMPLE: "block block-example",
    BlockType.COUNTEREXAMPLE: "block block-counterexample",
    BlockType.PROOF: "block block-proof",
    BlockType.VIZ: "block block-viz",
    BlockType.LAB: "block block-lab",
    BlockType.CHECK: "block block-check",
}


def _badge_html(block: Block) -> str:
    b = block.badge
    receipt = b.receipt
    detail = ""
    if receipt.kind.value != "none":
        detail = f'<span class="receipt">receipt: {html.escape(receipt.kind.value)}</span>'
    return (
        f'<span class="{_BADGE_CLASS[b.tier]}" title="{html.escape(str(receipt.detail))}">'
        f"{b.tier.value}</span>{detail}"
    )


def render_block_html(block: Block) -> str:
    cls = _BLOCK_CLASS[block.type]
    body = html.escape(block.text) if block.text else ""
    extra = ""
    if block.type in (BlockType.EXAMPLE, BlockType.CHECK) and block.ref:
        extra = f'<div class="ref">Foundry: <code>{html.escape(block.ref)}</code></div>'
    if block.type == BlockType.VIZ and block.template:
        extra = f'<div class="viz" data-template="{html.escape(block.template)}"></div>'
    if block.type == BlockType.LAB and block.runtime:
        extra = (
            f'<pre class="lab" data-runtime="{html.escape(block.runtime)}">'
            f"{html.escape(block.starter or '')}</pre>"
        )
    return (
        f'<section class="{cls}" data-block-id="{html.escape(block.id)}">'
        f"{_badge_html(block)}"
        f'<div class="body">{body}</div>{extra}</section>'
    )


def render_html(lesson: LessonIR, *, standalone: bool = True) -> str:
    """Render a lesson to HTML. ``standalone`` wraps it in a minimal document."""
    blocks = "\n".join(render_block_html(b) for b in lesson.blocks)
    overall = lesson.badge.value
    header = (
        f'<header class="lesson-header"><h1>{html.escape(lesson.title)}</h1>'
        f'<span class="overall-badge">{overall}</span></header>'
    )
    body = f"{header}\n{blocks}"
    if not standalone:
        return body
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(lesson.title)}</title>"
        "<style>" + _CSS + "</style></head><body>"
        f'<article class="lesson">{body}</article></body></html>'
    )


def render_audio_script(lesson: LessonIR) -> str:
    """A narration script. MODEL blocks are announced as unverified."""
    lines: list[str] = [lesson.title]
    for b in lesson.blocks:
        if not b.text:
            continue
        prefix = ""
        if b.badge.tier == Trust.MODEL:
            prefix = "(unverified) "
        lines.append(f"{prefix}{b.text}")
    return "\n\n".join(lines)


def render_chat_text(lesson: LessonIR) -> str:
    """Plain text for chat apps / bots, badges inline."""
    out = [f"*{lesson.title}*"]
    for b in lesson.blocks:
        if not b.text:
            continue
        out.append(f"[{b.badge.tier.value}] {b.text}")
    return "\n".join(out)


_CSS = """
:root{--bg:#0b0f14;--fg:#e6edf3;--muted:#8b949e;--line:#1f2630}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.lesson{max-width:760px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:1.6rem;margin:0 0 4px}
.lesson-header{display:flex;align-items:baseline;gap:12px;margin-bottom:20px}
.block{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:12px 0;position:relative}
.block-claim{border-left:3px solid #3fb950}
.block-proof{border-left:3px solid #58a6ff}
.block-example{border-left:3px solid #d29922}
.block-counterexample{border-left:3px solid #f85149}
.block-intuition{border-left:3px solid #a371f7}
.block-lab{border-left:3px solid #1f6feb}
.block-viz{border-left:3px solid #39c5cf}
.block-check{border-left:3px solid #db61a2}
.badge{position:absolute;top:12px;right:12px;font-size:.7rem;letter-spacing:.04em;
padding:2px 8px;border-radius:999px;border:1px solid var(--line)}
.badge-verified{color:#3fb950;border-color:#2ea04366}
.badge-sourced{color:#58a6ff;border-color:#388bfd66}
.badge-judged{color:#d29922;border-color:#9e6a0366}
.badge-model{color:var(--muted)}
.receipt{font-size:.7rem;color:var(--muted);margin-left:8px}
.ref,.viz,.lab{color:var(--muted);font-size:.85rem;margin-top:8px}
pre.lab{background:#010409;padding:10px;border-radius:8px;overflow:auto}
.overall-badge{font-size:.75rem;color:var(--muted)}
"""
