"""Trust tiers and receipts — the heart of EdGen's credibility.

Every learner-facing item carries a :class:`TrustBadge`. The tiers are ordered by
evidence strength:

- ``VERIFIED``  executed proof: oracle, tests, dual-solver agreement.
- ``SOURCED``   a span from a real source, with license metadata.
- ``JUDGED``    scored by an LLM or human against a rubric (never called "verified").
- ``MODEL``     generated, unverified. Factual MODEL claims are stripped or flagged.

ADR #11: trust badges on every item. This module is the single source of truth for
what a badge means and what receipt each one requires.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Trust(StrEnum):
    """Trust tier of a learner-facing item, strongest first."""

    VERIFIED = "VERIFIED"
    SOURCED = "SOURCED"
    JUDGED = "JUDGED"
    MODEL = "MODEL"


#: Tiers that are allowed to make a factual claim without being stripped/flagged.
FACTUAL_TIERS: frozenset[Trust] = frozenset({Trust.VERIFIED, Trust.SOURCED})

#: Badge strength, used to pick the weakest badge in a composition (e.g. a lesson).
_STRENGTH: dict[Trust, int] = {
    Trust.VERIFIED: 3,
    Trust.SOURCED: 2,
    Trust.JUDGED: 1,
    Trust.MODEL: 0,
}


class ReceiptKind(StrEnum):
    ORACLE = "oracle"
    TESTS = "tests"
    SOURCE_SPAN = "source_span"
    RUBRIC = "rubric"
    NONE = "none"


class Receipt(BaseModel):
    """Evidence backing a claim. Shape depends on ``kind``."""

    kind: ReceiptKind
    #: For oracle/tests receipts: the identifiers that produced the verdict.
    refs: list[str] = Field(default_factory=list)
    #: For source_span receipts.
    source_id: str | None = None
    span: tuple[int, int] | None = None
    license: str | None = None
    #: Free-form extras (e.g. seeds checked, solver versions).
    detail: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_shape(self) -> Receipt:
        if self.kind == ReceiptKind.SOURCE_SPAN:
            if self.source_id is None or self.span is None:
                raise ValueError("source_span receipt requires source_id and span")
            if self.span[0] > self.span[1]:
                raise ValueError("span start must be <= end")
        if self.kind in (ReceiptKind.ORACLE, ReceiptKind.TESTS) and not self.refs:
            raise ValueError(f"{self.kind} receipt requires at least one ref")
        return self


class TrustBadge(BaseModel):
    """A trust tier plus the receipt that justifies it."""

    tier: Trust
    receipt: Receipt

    @model_validator(mode="after")
    def _check_consistency(self) -> TrustBadge:
        expected = {
            Trust.VERIFIED: {ReceiptKind.ORACLE, ReceiptKind.TESTS},
            Trust.SOURCED: {ReceiptKind.SOURCE_SPAN},
            Trust.JUDGED: {ReceiptKind.RUBRIC},
            Trust.MODEL: {ReceiptKind.NONE},
        }[self.tier]
        if self.receipt.kind not in expected:
            raise ValueError(
                f"{self.tier} badge requires receipt kind in {sorted(expected)}, "
                f"got {self.receipt.kind}"
            )
        return self

    @classmethod
    def verified(cls, *refs: str, **detail: Any) -> TrustBadge:
        return cls(tier=Trust.VERIFIED, receipt=Receipt(kind=ReceiptKind.ORACLE, refs=list(refs), detail=detail))

    @classmethod
    def tested(cls, *refs: str, **detail: Any) -> TrustBadge:
        return cls(tier=Trust.VERIFIED, receipt=Receipt(kind=ReceiptKind.TESTS, refs=list(refs), detail=detail))

    @classmethod
    def sourced(cls, source_id: str, span: tuple[int, int], license: str) -> TrustBadge:
        return cls(
            tier=Trust.SOURCED,
            receipt=Receipt(kind=ReceiptKind.SOURCE_SPAN, source_id=source_id, span=span, license=license),
        )

    @classmethod
    def judged(cls, rubric_id: str, score: float | None = None) -> TrustBadge:
        detail = {} if score is None else {"score": score}
        return cls(tier=Trust.JUDGED, receipt=Receipt(kind=ReceiptKind.RUBRIC, refs=[rubric_id], detail=detail))

    @classmethod
    def model_generated(cls, **detail: Any) -> TrustBadge:
        return cls(tier=Trust.MODEL, receipt=Receipt(kind=ReceiptKind.NONE, detail=detail))

    @property
    def is_factual(self) -> bool:
        return self.tier in FACTUAL_TIERS

    @property
    def strength(self) -> int:
        return _STRENGTH[self.tier]


def weakest(badges: list[TrustBadge]) -> Trust:
    """A composite item (lesson, quest) is only as trustworthy as its weakest block."""
    if not badges:
        return Trust.MODEL
    return min(badges, key=lambda b: b.strength).tier


def factual_claim_allowed(badge: TrustBadge) -> bool:
    """MODEL factual claims must be stripped or flagged (SystemsDesign §5)."""
    return badge.is_factual


Label = Literal["VERIFIED", "SOURCED", "MODEL", "JUDGED"]
