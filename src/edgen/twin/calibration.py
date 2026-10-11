"""Calibration (SystemsDesign §3).

Learners state confidence before submitting. We track a Brier score and a
reliability curve per subject so the app can say: "when you say 70%, you're right
52% of the time." The Attempt Advisor uses the calibrated ``p``.
"""

from __future__ import annotations

from pydantic import BaseModel

#: Confidence buckets, in percent (GATE-style: 25/50/75/90).
CONF_BINS: tuple[int, ...] = (0, 25, 50, 75, 90, 100)


def bin_of(confidence: int) -> int:
    """Map a confidence percentage to its reliability-curve bucket."""
    best = CONF_BINS[0]
    for b in CONF_BINS:
        if confidence >= b:
            best = b
    return best


class CalibrationBin(BaseModel):
    subject: str
    conf_bin: int
    n: int = 0
    n_correct: int = 0
    brier_sum: float = 0.0

    @property
    def mean_confidence(self) -> float:
        return self.conf_bin / 100.0

    @property
    def empirical_accuracy(self) -> float:
        return self.n_correct / self.n if self.n else 0.0

    @property
    def brier(self) -> float:
        return self.brier_sum / self.n if self.n else 0.0


class CalibrationTracker:
    """Accumulates per-subject reliability curves and Brier scores."""

    def __init__(self) -> None:
        self._bins: dict[tuple[str, int], CalibrationBin] = {}

    def record(self, subject: str, confidence: int, correct: bool) -> CalibrationBin:
        key = (subject, bin_of(confidence))
        b = self._bins.get(key) or CalibrationBin(subject=subject, conf_bin=key[1])
        b.n += 1
        b.n_correct += int(correct)
        p = confidence / 100.0
        b.brier_sum += (p - float(correct)) ** 2
        self._bins[key] = b
        return b

    def bins(self, subject: str | None = None) -> list[CalibrationBin]:
        items = [b for (s, _), b in self._bins.items() if subject is None or s == subject]
        return sorted(items, key=lambda b: (b.subject, b.conf_bin))

    def brier(self, subject: str) -> float:
        bs = [b for b in self.bins(subject) if b.n]
        total = sum(b.n for b in bs)
        if not total:
            return 0.0
        return sum(b.brier_sum for b in bs) / total

    def calibrated_p(self, subject: str, stated_confidence: int) -> float:
        """Empirical accuracy for the stated-confidence bucket (the calibrated p).

        Falls back to the stated confidence when the bucket is thin, blending
        toward the empirical rate as evidence accumulates.
        """
        b = self._bins.get((subject, bin_of(stated_confidence)))
        stated = stated_confidence / 100.0
        if b is None or b.n == 0:
            return stated
        # Shrinkage: weight the empirical estimate by sample size (prior n0 = 5).
        n0 = 5.0
        return (b.n_correct + n0 * stated) / (b.n + n0)

    def reliability_curve(self, subject: str) -> list[dict]:
        return [
            {
                "conf_bin": b.conf_bin,
                "n": b.n,
                "mean_confidence": b.mean_confidence,
                "empirical_accuracy": b.empirical_accuracy,
            }
            for b in self.bins(subject)
        ]
