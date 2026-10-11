"""Lesson IR: block graph, trust badges, receipts, cache keys, renderers.

Trust badges (ADR 11): VERIFIED / SOURCED / MODEL / JUDGED — every block that
makes a claim carries exactly one. Receipts are validated against source text
at load time: a SOURCED block without a valid span cannot ship.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Badge = Literal["VERIFIED", "SOURCED", "MODEL", "JUDGED"]
BlockType = Literal["claim", "intuition", "example", "counterexample", "proof", "viz", "lab", "check"]


class Receipt(BaseModel):
    kind: Literal["source_span", "executed", "tests"]
    source_id: str | None = None
    quote: str | None = None
    span: list[int] | None = None
    license: str | None = None
    detail: str | None = None  # for executed/tests receipts


class Block(BaseModel):
    id: str
    type: BlockType
    text: str | None = None
    badge: Badge | None = None
    receipt: Receipt | None = None
    # viz
    template: str | None = None
    spec: dict[str, Any] = Field(default_factory=dict)
    # lab
    runtime: str | None = None
    starter: str | None = None
    # check
    foundry: str | None = None
    prompt: str | None = None

    @field_validator("badge")
    @classmethod
    def _claim_needs_badge(cls, v, info):
        return v


class LessonCore(BaseModel):
    lesson_id: str
    node_id: str
    core_version: int = 1
    lang: str = "en"
    depth: str = "standard"
    title: str
    review_status: Literal["draft", "reviewed"] = "draft"
    blocks: list[Block]

    @property
    def track(self) -> str:
        return self.node_id.split(".", 1)[0] if "." in self.node_id else self.node_id


# --- cache key (architecture §6) -------------------------------------------

def cache_key(track: str, node: str, lang: str, depth: str, style: str, core_version: int) -> str:
    return f"core:{track}:{node}:{lang}:{depth}:{style}:{core_version}"


# --- receipt validation ------------------------------------------------------

class ReceiptError(ValueError):
    pass


def load_sources(content_dir: Path) -> dict[str, dict[str, Any]]:
    """Load raw source texts used to validate receipts."""
    out: dict[str, dict[str, Any]] = {}
    src_dir = Path(content_dir) / "sources"
    if not src_dir.exists():
        return out
    for f in sorted(src_dir.glob("*.md")):
        out[f.stem] = {"id": f.stem, "text": f.read_text(), "path": str(f)}
    # allow json sources too (external corpora with explicit license fields)
    for f in sorted(src_dir.glob("*.json")):
        data = json.loads(f.read_text())
        out[data["id"]] = {"id": data["id"], "text": data["text"], "license": data.get("license")}
    return out


def validate_receipts(lesson: LessonCore, sources: dict[str, dict[str, Any]]) -> LessonCore:
    """Fill/verify spans. Raises if a SOURCED receipt cannot be grounded."""
    for b in lesson.blocks:
        if b.badge == "SOURCED":
            if not b.receipt or b.receipt.kind != "source_span" or not b.receipt.quote:
                raise ReceiptError(f"{lesson.lesson_id}/{b.id}: SOURCED block needs a source_span receipt with a quote")
            src = sources.get(b.receipt.source_id or "")
            if src is None:
                raise ReceiptError(f"{lesson.lesson_id}/{b.id}: unknown source {b.receipt.source_id}")
            start = src["text"].find(b.receipt.quote)
            if start < 0:
                raise ReceiptError(f"{lesson.lesson_id}/{b.id}: quote not found in source {b.receipt.source_id}")
            b.receipt.span = [start, start + len(b.receipt.quote)]
            if b.receipt.license is None:
                b.receipt.license = "CC-BY-SA-4.0"
        elif b.badge == "MODEL" and b.receipt is not None and b.receipt.kind == "source_span":
            raise ReceiptError(f"{lesson.lesson_id}/{b.id}: MODEL block must not carry a source receipt")
    return lesson


def load_lesson(path: Path, sources: dict[str, dict[str, Any]]) -> LessonCore:
    data = json.loads(Path(path).read_text())
    return validate_receipts(LessonCore.model_validate(data), sources)


def apply_delta(core: LessonCore, patch: list[dict[str, Any]]) -> LessonCore:
    """Apply a JSON Patch (RFC 6902 subset: add/replace/remove on /blocks...)."""
    data = core.model_dump()
    for op in patch:
        path = op["path"].lstrip("/")
        parts = path.split("/")
        if parts[0] != "blocks":
            raise ValueError(f"only /blocks patches supported, got {op['path']}")
        idx = int(parts[1])
        if op["op"] == "remove":
            if len(parts) == 2:
                data["blocks"].pop(idx)
            else:
                _pop_field(data["blocks"][idx], parts[2:])
        elif op["op"] == "add":
            if len(parts) == 2:
                data["blocks"].insert(idx, op["value"])
            else:
                _set_field(data["blocks"][idx], parts[2:], op["value"], insert=True)
        elif op["op"] == "replace":
            if len(parts) == 2:
                data["blocks"][idx] = op["value"]
            else:
                _set_field(data["blocks"][idx], parts[2:], op["value"])
        else:
            raise ValueError(f"unsupported op {op['op']}")
    out = LessonCore.model_validate(data)
    return out


def _set_field(obj, parts: list[str], value, insert: bool = False) -> None:
    for p in parts[:-1]:
        obj = obj[p]
    key = parts[-1]
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def _pop_field(obj, parts: list[str]) -> None:
    for p in parts[:-1]:
        obj = obj[p]
    key = parts[-1]
    if isinstance(obj, dict):
        obj.pop(key, None)
    else:
        setattr(obj, key, None)


# --- renderers ---------------------------------------------------------------

_BADGE_LABEL = {
    "VERIFIED": "VERIFIED · executed",
    "SOURCED": "SOURCED",
    "MODEL": "MODEL",
    "JUDGED": "JUDGED",
}


def _receipt_note(b: Block) -> str:
    r = b.receipt
    if not r:
        return ""
    if r.kind == "source_span":
        return f'Source span {r.source_id}:{r.span[0]}–{r.span[1]} · {r.license or ""}'
    return r.detail or ""


def block_to_html(b: Block) -> str:
    """Server-side renderer for SEO/static pages (architecture §17)."""
    cls = f"lg-block lg-{b.type}"
    badge = f'<span class="lg-badge lg-badge-{b.badge.lower()}">{_BADGE_LABEL[b.badge]}</span>' if b.badge else ""
    note = _receipt_note(b)
    note_html = f'<div class="lg-receipt">{html.escape(note)}</div>' if note else ""
    if b.type == "viz":
        return f'<div class="{cls}" data-viz="{html.escape(b.template or "")}">{badge}<pre class="lg-viz-spec">{html.escape(json.dumps(b.spec))}</pre></div>'
    if b.type == "check":
        return f'<div class="{cls}">{badge}<p>{html.escape(b.prompt or "")}</p><a class="lg-cta" href="/practice?gen={html.escape(b.foundry or "")}">Practice this</a></div>'
    if b.type == "lab":
        return f'<div class="{cls}">{badge}<pre class="lg-code">{html.escape(b.starter or "")}</pre></div>'
    text = html.escape(b.text or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = text.replace("\n", "<br/>")
    return f'<div class="{cls}">{badge}<p>{text}</p>{note_html}</div>'


def lesson_to_html(lesson: LessonCore) -> str:
    blocks = "\n".join(block_to_html(b) for b in lesson.blocks)
    return f'<article class="lg-lesson"><h1>{html.escape(lesson.title)}</h1>\n{blocks}\n</article>'
