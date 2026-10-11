"""Attempt Advisor (SystemsDesign §4).

GATE marking rules (verify each cycle against the official site):
- MCQ 1-mark: +1 correct, −1/3 wrong  → attempt when ``p > 1/4``.
- MCQ 2-mark: +2 correct, −2/3 wrong  → attempt when ``p > 1/4`` (same threshold).
- MSQ and NAT: no negative marking → always attempt. MSQ has no partial marking,
  so it requires every correct option.

The advisor takes the learner's *calibrated* p (from the Twin), not their raw
stated confidence.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

#: MCQ penalty as a fraction of the question's marks (1/3 or 2/3).
MCQ_PENALTY_FRACTION = 1.0 / 3.0
#: Break-even probability for MCQ. EV = p·m − (1−p)·m/3 = m·(4p−1)/3, which is
#: positive iff p > 1/4. Both the 1-mark (1/3) and 2-mark (2/3) penalties give the
#: same 1/4 threshold because the penalty scales with the marks.
MCQ_BREAKEVEN_P = 0.25


class QuestionType(StrEnum):
    MCQ = "mcq"
    MSQ = "msq"
    NAT = "nat"


class AttemptAdvice(BaseModel):
    question_type: QuestionType
    calibrated_p: float
    threshold: float
    recommend: str  # "attempt" | "skip"
    expected_value: float
    reason: str


def _mcq_ev(p: float, marks: int) -> float:
    penalty = marks * MCQ_PENALTY_FRACTION
    return p * marks - (1.0 - p) * penalty


def advise_attempt(
    *,
    question_type: QuestionType,
    calibrated_p: float,
    marks: int = 1,
    all_options_known: bool = True,
) -> AttemptAdvice:
    """Recommend attempt/skip with the expected value that justifies it."""
    p = min(max(calibrated_p, 0.0), 1.0)

    if question_type == QuestionType.MCQ:
        ev = _mcq_ev(p, marks)
        recommend = "attempt" if ev > 0 else "skip"
        reason = (
            f"MCQ {marks}-mark penalty is {marks}×1/3; attempt pays off when "
            f"p > {MCQ_BREAKEVEN_P:.2f}."
        )
        return AttemptAdvice(
            question_type=question_type,
            calibrated_p=p,
            threshold=MCQ_BREAKEVEN_P,
            recommend=recommend,
            expected_value=round(ev, 4),
            reason=reason,
        )

    if question_type == QuestionType.MSQ:
        # No negative marking, no partial credit: attempt only if you know every
        # correct option, else the expected value can be negative in practice.
        recommend = "attempt" if all_options_known else "skip"
        reason = (
            "MSQ has no negative marking but no partial credit; attempt only when "
            "you are confident of every correct option."
        )
        return AttemptAdvice(
            question_type=question_type,
            calibrated_p=p,
            threshold=0.0,
            recommend=recommend,
            expected_value=round(p * marks, 4),
            reason=reason,
        )

    # NAT: no negative marking — always attempt.
    return AttemptAdvice(
        question_type=QuestionType.NAT,
        calibrated_p=p,
        threshold=0.0,
        recommend="attempt",
        expected_value=round(p * marks, 4),
        reason="NAT has no negative marking; always attempt.",
    )
