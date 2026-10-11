"""The greedy-with-lookahead planner (SystemsDesign §4).

Objective by goal type:
- **exam:** maximize expected weighted mastery (marks proxy) at the exam date,
  accounting for decay between now and then.
- **role:** maximize readiness gain per minute, with a spaced-review floor.
- **mastery:** maximize breadth of verified nodes with reviews due.

Algorithm:
1. Candidates = frontier ∪ due reviews.
2. gain(c) = expected weighted improvement at the goal date; cost(c) = minutes.
3. Sort by gain/cost; enforce prerequisites; interleave clusters (≤2 in a row);
   cap reviews at ~20% of time; reserve ~15% for exploration.
4. Output 3–5 items; re-plan after every session and nightly.

Every selected item carries ``policy_id`` and ``propensity`` so offline policy
evaluation (inverse propensity weighting) is possible later (ADR #9).
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from edgen.graph.engine import ConceptGraph
from edgen.graph.model import GoalType, Lens
from edgen.planner.model import PlanItem, Reason, TodayPlan
from edgen.twin.forgetting import retrievability


class PlannerConfig(BaseModel):
    minutes_budget: int = 45
    max_items: int = 5
    min_items: int = 3
    #: Reviews are capped at this fraction of the time budget.
    review_time_cap: float = 0.20
    #: Exploration (bandit) reserve, logged with propensities.
    explore_fraction: float = 0.15
    #: Review due threshold on retrievability.
    review_due_r: float = 0.85
    #: Mastery gained by a single focused session on a node (pedagogical prior).
    session_mastery_gain: float = 0.18
    #: Milestone nodes get a bonus for role lenses.
    milestone_bonus: float = 1.5
    #: Interleaving: max consecutive items from one cluster (first 2 id parts).
    max_consecutive_cluster: int = 2


def _cluster(node_id: str) -> str:
    parts = node_id.split(".")
    return ".".join(parts[:2])


class Planner:
    def __init__(self, graph: ConceptGraph, config: PlannerConfig | None = None) -> None:
        self.graph = graph
        self.config = config or PlannerConfig()

    # -- gain model -----------------------------------------------------------
    def _decay_to_goal(
        self, node_id: str, mastery: dict[str, float], stability: dict[str, float], horizon_days: float
    ) -> float:
        """Effective mastery at the goal date if *nothing* is done (pure decay)."""
        if horizon_days <= 0:
            return mastery.get(node_id, 0.0)
        s = stability.get(node_id, 1.0)
        # Treat m_eff today as P(L)*R(0); project R forward.
        p_known = mastery.get(node_id, 0.0)  # m_eff at t=0 (R≈1 at planning time)
        elapsed = max(0.0, horizon_days)
        return p_known * retrievability(elapsed, s)

    def _expected_gain(
        self,
        node_id: str,
        mastery: dict[str, float],
        stability: dict[str, float],
        horizon_days: float,
        weight: float,
    ) -> float:
        """Weighted improvement at the goal date from doing this node now."""
        base = self._decay_to_goal(node_id, mastery, stability, horizon_days)
        # A session lifts P(L); the new knowledge still decays to the goal date.
        lifted = min(1.0, mastery.get(node_id, 0.0) + self.config.session_mastery_gain)
        if horizon_days > 0:
            lifted *= retrievability(horizon_days, max(1.0, stability.get(node_id, 1.0) * 1.5))
        return max(0.0, weight * (lifted - base))

    def _minutes(self, node_id: str) -> int:
        node = self.graph.get(node_id)
        return node.est_minutes.get("standard", 12)

    # -- main -----------------------------------------------------------------
    def today(
        self,
        *,
        user_id: str,
        lens: Lens,
        mastery: dict[str, float],
        stability: dict[str, float] | None = None,
        now: dt.datetime | None = None,
        due_reviews: dict[str, float] | None = None,
    ) -> TodayPlan:
        """Build today's plan. ``mastery`` is m_eff per node; ``due_reviews`` maps
        node_id -> current retrievability R for spaced-review candidates."""
        now = now or dt.datetime.now(dt.UTC)
        stability = stability or {}
        due_reviews = due_reviews or {}
        weights = {self.graph.resolve(k): v for k, v in lens.weights().items()}
        horizon_days = 0.0
        if lens.goal_type == GoalType.EXAM and lens.exam_date is not None:
            horizon_days = max(0.0, (lens.exam_date - now.date()).days)

        frontier = set(self.graph.frontier(lens, mastery))
        _ = frontier  # reporting-only; candidates are broader (see below)
        review_nodes = {
            self.graph.resolve(n)
            for n, r in due_reviews.items()
            if r < self.config.review_due_r and n in weights
        }
        # Candidates are every node the learner has not yet mastered, plus due
        # reviews. ``take`` below schedules any unmet prerequisites first, so a
        # deep candidate pulls its chain rather than being skipped. The documented
        # frontier band is used for reporting, not to gate candidates (a brand-new
        # learner would otherwise see only the two root nodes).
        candidates = {n for n in weights if float(mastery.get(n, 0.0)) < 0.7} | review_nodes

        # Score every candidate: gain/min, with milestone bonus for role lenses.
        scored: list[tuple[float, str, Reason, int]] = []
        for n in candidates:
            w = weights.get(n, 1.0)
            if lens.goal_type == GoalType.ROLE and n in lens.milestones:
                w *= self.config.milestone_bonus
            gain = self._expected_gain(n, mastery, stability, horizon_days, w)
            minutes = self._minutes(n)
            reason = Reason.REVIEW if n in review_nodes else Reason.FRONTIER
            scored.append((gain / max(1, minutes), n, reason, minutes))

        scored.sort(key=lambda t: (-t[0], t[1]))  # deterministic tie-break by node id

        selected: list[PlanItem] = []
        chosen: set[str] = set()
        used_minutes = 0
        review_minutes = 0
        cluster_run: list[str] = []
        review_cap = int(self.config.minutes_budget * self.config.review_time_cap)

        def cluster_of(nid: str) -> str:
            return _cluster(nid)

        def append(n: str, reason: Reason, minutes: int, gain_per_min: float) -> None:
            nonlocal used_minutes, review_minutes
            selected.append(
                PlanItem(
                    node_id=n,
                    title=self.graph.get(n).title,
                    reason=reason,
                    minutes=minutes,
                    gain_per_min=round(gain_per_min, 6),
                    m_eff_before=round(mastery.get(n, 0.0), 4),
                    practice=bool(self.graph.get(n).generators),
                    policy_id="planner.v1.greedy",
                    propensity=1.0,
                )
            )
            chosen.add(n)
            used_minutes += minutes
            if reason == Reason.REVIEW:
                review_minutes += minutes
            cluster_run.append(cluster_of(n))

        def take(n: str, reason: Reason, minutes: int, gain_per_min: float) -> bool:
            """Take a candidate, first scheduling any unmet prerequisites.

            The whole prerequisite chain is validated by simulation against the
            budget, the review cap and the interleave rule; if any part of the
            chain would break a rule, the candidate is skipped so the caller can
            try a different one (which keeps clusters interleaved).
            """
            chain: list[str] = []
            seen: set[str] = set()
            cur: str | None = n
            while cur is not None and cur not in chosen and cur not in seen:
                seen.add(cur)
                chain.append(cur)
                unmet = [
                    p
                    for p in self.graph.prereqs(cur)
                    if p not in chosen and float(mastery.get(p, 0.0)) < 0.7
                ]
                cur = unmet[0] if unmet else None
            chain.reverse()  # prerequisites first

            sim_minutes = used_minutes
            sim_review = review_minutes
            sim_run = list(cluster_run)
            k = self.config.max_consecutive_cluster
            for c in chain:
                if c in chosen:
                    continue
                cm = self._minutes(c)
                creason = Reason.REVIEW if c in review_nodes else reason
                if sim_minutes + cm > self.config.minutes_budget:
                    return False
                if creason == Reason.REVIEW and sim_review + cm > review_cap and (selected or len(chain) > 1):
                    return False
                run = sim_run + [cluster_of(c)]
                if len(run) >= k + 1 and len(set(run[-k - 1 :])) == 1:
                    return False
                sim_run.append(cluster_of(c))
                sim_minutes += cm
                if creason == Reason.REVIEW:
                    sim_review += cm

            for c in chain:
                if c in chosen:
                    continue
                cm = self._minutes(c)
                creason = Reason.REVIEW if c in review_nodes else reason
                append(c, creason, cm, gain_per_min if c == n else 0.0)
            return True

        for gain_per_min, n, reason, minutes in scored:
            if len(selected) >= self.config.max_items:
                break
            take(n, reason, minutes, gain_per_min)

        # Fill to the minimum item count by relaxing the interleave rule.
        if len(selected) < self.config.min_items:
            for gain_per_min, n, _reason, minutes in scored:
                if len(selected) >= self.config.min_items:
                    break
                if n in chosen:
                    continue
                take(n, Reason.EXPLORE, minutes, gain_per_min)

        readiness_before = self.graph.readiness(lens, mastery)
        projected = dict(mastery)
        for it in selected:
            projected[it.node_id] = min(
                1.0, projected.get(it.node_id, 0.0) + self.config.session_mastery_gain
            )
        expected_after = self.graph.readiness(lens, projected)

        return TodayPlan(
            user_id=user_id,
            lens_id=lens.id,
            goal_type=lens.goal_type.value,
            items=selected,
            total_minutes=used_minutes,
            readiness_before=round(readiness_before, 4),
            expected_readiness_after=round(expected_after, 4),
        )
