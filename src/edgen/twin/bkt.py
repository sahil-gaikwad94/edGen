"""Bayesian Knowledge Tracing (SystemsDesign §3).

Per-skill parameters: ``p_init, p_learn, p_slip, p_guess``. Hinted-correct answers
count as weaker evidence: each hint level inflates ``guess`` (the probability of a
lucky correct), which shrinks the posterior gain from a correct answer.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

#: Guess inflation per hint level (calibrate on data). Level 0 -> x1, level 4 -> x3.
HINT_GUESS_MULTIPLIER: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0, 3.0)


class BKTParams(BaseModel):
    p_init: float = 0.15
    p_learn: float = 0.20
    p_slip: float = 0.10
    p_guess: float = 0.20

    @field_validator("p_init", "p_learn", "p_slip", "p_guess")
    @classmethod
    def _unit(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("BKT probabilities must be in [0, 1]")
        return v

    @field_validator("p_slip", "p_guess")
    @classmethod
    def _not_certain(cls, v: float) -> float:
        # slip + guess == 1 would make observations uninformative.
        if v >= 1.0:
            raise ValueError("slip and guess must be < 1")
        return v


def hint_guess(guess: float, hint_level: int) -> float:
    """Inflate the guess rate for a hinted answer, clamped to just below 1."""
    idx = min(max(hint_level, 0), len(HINT_GUESS_MULTIPLIER) - 1)
    return min(0.999, guess * HINT_GUESS_MULTIPLIER[idx])


def posterior_given_correct(p_known: float, slip: float, guess: float) -> float:
    """``P(L|c) = P(L)(1-slip) / [P(L)(1-slip) + (1-P(L))·guess]``."""
    num = p_known * (1.0 - slip)
    den = num + (1.0 - p_known) * guess
    return num / den if den > 0 else p_known


def posterior_given_wrong(p_known: float, slip: float, guess: float) -> float:
    """``P(L|w) = P(L)·slip / [P(L)·slip + (1-P(L))(1-guess)]``."""
    num = p_known * slip
    den = num + (1.0 - p_known) * (1.0 - guess)
    return num / den if den > 0 else p_known


def update(
    p_known: float,
    correct: bool,
    params: BKTParams,
    *,
    hint_level: int = 0,
) -> float:
    """Full BKT step: evidence update, then learning transition.

    ``P(L') = P(L|obs) + (1 - P(L|obs))·p_learn``.
    """
    guess = hint_guess(params.p_guess, hint_level)
    p_obs = (
        posterior_given_correct(p_known, params.p_slip, guess)
        if correct
        else posterior_given_wrong(p_known, params.p_slip, guess)
    )
    return p_obs + (1.0 - p_obs) * params.p_learn


class MasteryState(BaseModel):
    """Per (user, node) mastery state."""

    node_id: str
    p_known: float = 0.15
    stability_days: float = 1.0
    attempts: int = 0
    last_seen: dt.datetime | None = None
    params: BKTParams = Field(default_factory=BKTParams)

    def apply(self, correct: bool, *, hint_level: int = 0) -> MasteryState:
        self.p_known = update(self.p_known, correct, self.params, hint_level=hint_level)
        self.attempts += 1
        return self
