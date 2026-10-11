"""Bayesian Knowledge Tracing + FSRS-style forgetting (SystemsDesign §3).

All functions are pure; persistence lives in the API's attempt log. The Twin is
rebuildable from attempts alone (architecture §7 recompute path).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


# --- BKT ------------------------------------------------------------------

@dataclass(frozen=True)
class BKTParams:
    p_learn: float = 0.18
    p_slip: float = 0.10
    p_guess: float = 0.20

    def effective_guess(self, hint_level: int = 0) -> float:
        """Hints inflate guess: a hinted-correct answer is weaker evidence.

        Calibration of the per-level inflation happens on data; W0 uses +0.10/level.
        """
        return min(0.80, self.p_guess + 0.10 * max(0, hint_level))


def bkt_step(
    p_known: float,
    correct: bool,
    params: BKTParams = BKTParams(),
    hint_level: int = 0,
) -> float:
    """One BKT update; returns P(L') in [0, 1]."""
    p = min(1.0, max(0.0, p_known))
    guess = params.effective_guess(hint_level)
    slip = params.p_slip
    if correct:
        posterior = (p * (1 - slip)) / (p * (1 - slip) + (1 - p) * guess + 1e-12)
    else:
        posterior = (p * slip) / (p * slip + (1 - p) * (1 - guess) + 1e-12)
    p_next = posterior + (1 - posterior) * params.p_learn if correct else posterior
    return min(1.0, max(0.0, p_next))


# --- Forgetting (FSRS-style, SystemsDesign §3) -----------------------------

def retention(stability_days: float, days_elapsed: float) -> float:
    """R(Δt) = (1 + Δt / (9·S))^(−1); R = 0.9 when Δt = S."""
    s = max(0.05, stability_days)
    dt = max(0.0, days_elapsed)
    return (1.0 + dt / (9.0 * s)) ** -1.0


def review_stability(stability_days: float, days_elapsed: float, success: bool) -> float:
    """Stability update after a spaced review.

    Success grows stability in proportion to how well it was remembered
    (easy reviews — high R — grow more); failure collapses it. Per-node/learner
    constants are learned later; W0 ships these documented approximations.
    """
    s = max(0.05, stability_days)
    r = retention(s, days_elapsed)
    if success:
        return min(3650.0, max(s, max(days_elapsed, 0.5)) * (0.6 + r))
    return max(1.0, s * 0.25)


def m_eff(p_known: float, stability_days: float, days_elapsed: float) -> float:
    """Effective mastery = P(L) · R."""
    return min(1.0, max(0.0, p_known)) * retention(stability_days, days_elapsed)


# --- Twin state -------------------------------------------------------------

@dataclass
class TwinState:
    user_id: str
    node_id: str
    p_known: float
    stability_days: float = 30.0
    last_seen_days: float = 0.0  # days since last touch, set by caller
    attempts: int = 0
    error_tags: dict[str, int] = field(default_factory=dict)

    @property
    def retention_now(self) -> float:
        return retention(self.stability_days, self.last_seen_days)

    @property
    def m_eff_now(self) -> float:
        return m_eff(self.p_known, self.stability_days, self.last_seen_days)

    def apply_attempt(
        self,
        correct: bool,
        *,
        params: BKTParams = BKTParams(),
        hint_level: int = 0,
        error_tag: str | None = None,
        confidence: int | None = None,
    ) -> "TwinState":
        """Pure update: returns the new state (logging happens outside)."""
        p = bkt_step(self.p_known, correct, params, hint_level)
        tags = dict(self.error_tags)
        if not correct and error_tag:
            tags[error_tag] = tags.get(error_tag, 0) + 1
        elif correct and error_tag:
            # a later correct answer on the same tag is evidence of repair
            if error_tag in tags:
                tags[error_tag] = max(0, tags[error_tag] - 1)
        if correct:
            new_stab = review_stability(self.stability_days, self.last_seen_days, success=True)
        else:
            new_stab = review_stability(self.stability_days, self.last_seen_days, success=False)
        # Correct evidence also refreshes recency; wrong answers keep decaying.
        new_seen = 0.0 if correct else self.last_seen_days
        return replace(
            self,
            p_known=p,
            stability_days=new_stab,
            last_seen_days=new_seen,
            attempts=self.attempts + 1,
            error_tags=tags,
        )


# --- Calibration ------------------------------------------------------------

CONF_BINS = (25, 50, 75, 90)


def conf_bin(confidence: int) -> int:
    """Map a stated confidence (25/50/75/90) onto its bin centre."""
    return min(CONF_BINS, key=lambda c: abs(c - confidence))


def brier_score(outcomes: list[tuple[int, int]]) -> float | None:
    """outcomes: [(confidence_pct, correct 0/1)] → mean squared calibration error."""
    if not outcomes:
        return None
    return sum(((c / 100.0) - y) ** 2 for c, y in outcomes) / len(outcomes)


def reliability_curve(bins: dict[int, tuple[int, int]]) -> list[dict]:
    """bins: {bin_centre: (n, n_correct)} → [{conf, observed, n}] where n>0."""
    out = []
    for b in sorted(bins):
        n, nc = bins[b]
        if n > 0:
            out.append({"conf": b, "observed": round(nc / n, 3), "n": n})
    return out
