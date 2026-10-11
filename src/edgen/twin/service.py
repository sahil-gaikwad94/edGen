"""Twin service — the personal learner model (SystemsDesign §3, architecture §7).

Responsibilities:
- apply BKT + FSRS updates per attempt (idempotent on ``attempt.id``),
- expose effective mastery maps for the graph/planner,
- track calibration and the Error Genome (mistake-type counts),
- log ``policy_id`` + ``propensity`` on every personalization decision (ADR #9).

The Twin can always be rebuilt from the ``attempt`` log; this service is the
incremental fold over that log.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass

from edgen.twin.bkt import BKTParams, MasteryState
from edgen.twin.calibration import CalibrationTracker
from edgen.twin.forgetting import effective_mastery, next_stability


@dataclass(frozen=True)
class Attempt:
    """A single graded attempt. ``id`` is client-generated (UUIDv7) for idempotency."""

    id: str
    user_id: str
    node_id: str
    correct: bool
    ts: dt.datetime
    confidence: int | None = None
    hint_level: int = 0
    latency_ms: int | None = None
    error_tag: str | None = None
    policy_id: str | None = None
    propensity: float | None = None
    subject: str | None = None


class Twin:
    """In-memory learner model. Swap the backing store for Postgres in prod."""

    def __init__(self, user_id: str, *, params: BKTParams | None = None) -> None:
        self.user_id = user_id
        self._params = params or BKTParams()
        self._states: dict[str, MasteryState] = {}
        self._seen_attempts: set[str] = set()
        self.calibration = CalibrationTracker()
        self.error_counts: Counter[str] = Counter()

    # -- state access ---------------------------------------------------------
    def state(self, node_id: str) -> MasteryState:
        st = self._states.get(node_id)
        if st is None:
            st = MasteryState(node_id=node_id, p_known=self._params.p_init, params=self._params)
            self._states[node_id] = st
        return st

    def p_known(self, node_id: str) -> float:
        return self._states[node_id].p_known if node_id in self._states else self._params.p_init

    def mastery_map(self, now: dt.datetime) -> dict[str, float]:
        """Effective mastery ``m_eff = P(L)·R`` per node, as of ``now``."""
        out: dict[str, float] = {}
        for node_id, st in self._states.items():
            elapsed = max(0.0, (now - st.last_seen).total_seconds() / 86400.0) if st.last_seen else 0.0
            out[node_id] = effective_mastery(st.p_known, elapsed, st.stability_days)
        return out

    # -- updates --------------------------------------------------------------
    def apply(self, attempt: Attempt) -> MasteryState:
        """Fold one attempt into the Twin. Idempotent on ``attempt.id``."""
        if attempt.id in self._seen_attempts:
            return self.state(attempt.node_id)
        self._seen_attempts.add(attempt.id)

        st = self.state(attempt.node_id)
        elapsed = (
            max(0.0, (attempt.ts - st.last_seen).total_seconds() / 86400.0) if st.last_seen else 0.0
        )
        st.stability_days = next_stability(st.stability_days, elapsed, attempt.correct)
        st.apply(attempt.correct, hint_level=attempt.hint_level)
        st.last_seen = attempt.ts

        if attempt.confidence is not None and attempt.subject:
            self.calibration.record(attempt.subject, attempt.confidence, attempt.correct)
        if not attempt.correct and attempt.error_tag:
            self.error_counts[attempt.error_tag] += 1
        return st

    def apply_many(self, attempts: list[Attempt]) -> None:
        for a in sorted(attempts, key=lambda x: x.ts):
            self.apply(a)

    # -- Error Genome ---------------------------------------------------------
    def error_genome(self, top: int = 10) -> list[dict]:
        """Most frequent mistake types for this learner, across tracks."""
        return [{"tag": tag, "count": n} for tag, n in self.error_counts.most_common(top)]
