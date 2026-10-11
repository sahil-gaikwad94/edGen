"""FSRS-style forgetting curve (SystemsDesign §3).

``R(Δt) = (1 + Δt / (9·S))^(-1)`` so that ``R = 0.9`` exactly when ``Δt = S``.
Stability ``S`` (in days) grows with successful spaced reviews and shrinks on
failure; it is tracked per (node, learner), never a fixed constant.
"""

from __future__ import annotations

import math

#: Stability multiplier applied on a successful review, scaled by how "due" the
#: item was. A review near the recall threshold (R≈0.9) is most valuable.
_GROWTH_MAX = 2.4
_GROWTH_MIN = 1.05
#: Multiplier applied on a failed review (lapse).
_LAPSE_MULTIPLIER = 0.5
MIN_STABILITY_DAYS = 0.1
MAX_STABILITY_DAYS = 3650.0


def retrievability(elapsed_days: float, stability_days: float) -> float:
    """Probability of recall after ``elapsed_days`` given stability ``S``.

    At ``Δt = S`` returns 0.9 by construction.
    """
    if stability_days <= 0:
        raise ValueError("stability_days must be positive")
    elapsed = max(0.0, float(elapsed_days))
    return (1.0 + elapsed / (9.0 * stability_days)) ** -1.0


def next_stability(stability_days: float, elapsed_days: float, correct: bool) -> float:
    """Update stability after a review.

    Successful review: grow stability, more when the review was well-timed (R
    near 0.9) and less when it was trivially easy (R near 1). Failed review:
    lapse — halve stability so the item resurfaces sooner.
    """
    s = max(MIN_STABILITY_DAYS, stability_days)
    if not correct:
        return max(MIN_STABILITY_DAYS, s * _LAPSE_MULTIPLIER)
    r = retrievability(elapsed_days, s)
    # r in (0,1]; "difficulty" peaks near r=0.9 -> multiplier near _GROWTH_MAX.
    closeness = 1.0 - abs(r - 0.9) / 0.9
    multiplier = _GROWTH_MIN + (_GROWTH_MAX - _GROWTH_MIN) * max(0.0, min(1.0, closeness))
    return min(MAX_STABILITY_DAYS, s * multiplier)


def days_until(target_r: float, stability_days: float) -> float:
    """Days until recall decays to ``target_r`` (invert the curve)."""
    if not 0.0 < target_r < 1.0:
        raise ValueError("target_r must be in (0, 1)")
    return 9.0 * stability_days * (target_r ** -1.0 - 1.0)


def effective_mastery(p_known: float, elapsed_days: float, stability_days: float) -> float:
    """``m_eff = P(L) · R`` — mastery discounted by forgetting."""
    return p_known * retrievability(elapsed_days, stability_days)


def log_loss(p: float, outcome: float) -> float:
    """Numerically safe binary log loss for calibration scoring."""
    p = min(max(p, 1e-9), 1.0 - 1e-9)
    return -(outcome * math.log(p) + (1.0 - outcome) * math.log(1.0 - p))
