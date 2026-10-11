"""Trust tiers and receipts must be internally consistent (ADR #11)."""

from __future__ import annotations

import pytest

from edgen.trust import (
    Receipt,
    ReceiptKind,
    Trust,
    TrustBadge,
    factual_claim_allowed,
    weakest,
)


def test_verified_requires_oracle_or_tests_receipt():
    with pytest.raises(ValueError):
        TrustBadge(tier=Trust.VERIFIED, receipt=Receipt(kind=ReceiptKind.NONE))
    with pytest.raises(ValueError):
        TrustBadge(tier=Trust.VERIFIED, receipt=Receipt(kind=ReceiptKind.SOURCE_SPAN,
                                                        source_id="x", span=(0, 1)))


def test_sourced_requires_span_and_license():
    with pytest.raises(ValueError):
        Receipt(kind=ReceiptKind.SOURCE_SPAN, source_id="x")  # missing span
    badge = TrustBadge.sourced("doc", (10, 20), "cc-by")
    assert badge.tier is Trust.SOURCED
    assert badge.receipt.span == (10, 20)
    assert badge.receipt.license == "cc-by"


def test_span_order_enforced():
    with pytest.raises(ValueError):
        Receipt(kind=ReceiptKind.SOURCE_SPAN, source_id="x", span=(20, 10))


def test_model_is_not_factual():
    assert not factual_claim_allowed(TrustBadge.model_generated())
    assert factual_claim_allowed(TrustBadge.verified("g@1"))
    assert factual_claim_allowed(TrustBadge.sourced("s", (0, 1), "cc0"))


def test_weakest_badge_dominates():
    badges = [
        TrustBadge.verified("g@1"),
        TrustBadge.sourced("s", (0, 1), "cc0"),
        TrustBadge.model_generated(),
    ]
    assert weakest(badges) is Trust.MODEL
    assert weakest([TrustBadge.verified("a"), TrustBadge.sourced("s", (0, 1), "cc0")]) is Trust.SOURCED
    assert weakest([]) is Trust.MODEL


def test_strength_ordering():
    assert TrustBadge.verified("a").strength > TrustBadge.sourced("s", (0, 1), "cc").strength
    assert TrustBadge.sourced("s", (0, 1), "cc").strength > TrustBadge.judged("r").strength
    assert TrustBadge.judged("r").strength > TrustBadge.model_generated().strength
