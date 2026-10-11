"""Daily planner (SystemsDesign §4).

Algorithm: candidates = frontier ∪ due reviews ∪ remediation → gain/cost sort
→ prerequisite order → interleave clusters (≤2 consecutive) → review cap 20% →
~15% exploration bandit slice → 3–5 items. Deterministic given inputs + seed.
Every item carries policy_id and propensity (ADR 9: log propensities day one).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Iterable, Protocol

POLICY_ID = "planner_greedy_v1"
EXPLORE_RATE = 0.15
REVIEW_CAP = 0.20
MIN_ITEMS, MAX_ITEMS = 3, 5


@dataclass
class Item:
    type: str  # lesson | practice | review | repair
    node_id: str
    est_min: int
    reason: str
    policy_id: str = POLICY_ID
    propensity: float = 1.0
    generator_id: str | None = None
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "node_id": self.node_id,
            "est_min": self.est_min,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "propensity": round(self.propensity, 6),
            "generator_id": self.generator_id,
            "meta": self.meta,
        }


@dataclass
class NodeInfo:
    id: str
    title: str
    topic: str
    weight: float
    m_eff: float  # effective mastery now
    retention: float  # R now
    p_known: float
    est_minutes: int
    prereqs: tuple[str, ...] = ()
    generators: tuple[str, ...] = ()
    has_lesson: bool = False
    error_count: int = 0
    attempts: int = 0


class PlannerInput(Protocol):
    pass


@dataclass
class PlanContext:
    lens_id: str
    goal_type: str  # exam | role | mastery
    goal_date: date | None
    minutes_budget: int
    now: date
    nodes: dict[str, NodeInfo]
    frontier: list[str]
    remediation: list[str]
    review_due: list[str]  # p_known ≥ 0.7 but R < 0.85
    seed: int = 0


def _retention_at(stability_days: float, days: float) -> float:
    from math import inf  # local import to avoid hard dep

    s = max(0.05, stability_days)
    return (1.0 + max(0.0, days) / (9.0 * s)) ** -1.0


def plan(ctx: PlanContext) -> tuple[list[Item], dict]:
    """Produce the day's plan. Returns (items, log) — log carries the seed and
    candidate sets so nightly recompute / offline evaluation can replay it."""
    rng = random.Random(ctx.seed)
    items: list[Item] = []
    used: set[str] = set()
    budget = max(15, ctx.minutes_budget)

    # --- candidates with gain/cost -----------------------------------------
    cands: list[tuple[float, str, str]] = []  # (gain_per_min, node_id, kind)
    days_to_goal = None
    if ctx.goal_date:
        days_to_goal = max(0.0, (ctx.goal_date - ctx.now).days)

    def decay(days: float | None) -> float:
        # rough retention factor at the goal date (stability ~14d for planning)
        if days is None:
            return 1.0
        return _retention_at(14.0, days)

    for nid in ctx.frontier:
        n = ctx.nodes.get(nid)
        if not n:
            continue
        gain = n.weight * (min(1.0, n.m_eff + 0.25) - n.m_eff) * decay(days_to_goal)
        # authored lesson → lesson; generator-backed → practice; else scaffold lesson
        kind = "lesson" if n.has_lesson else ("practice" if n.generators else "lesson")
        cands.append((gain / max(4.0, n.est_minutes), nid, kind))

    for nid in ctx.remediation:
        n = ctx.nodes.get(nid)
        if not n:
            continue
        gain = n.weight * (0.7 - n.m_eff) * decay(days_to_goal) * 1.1  # repair bonus
        kind = "lesson" if n.has_lesson else ("practice" if n.generators else "lesson")
        cands.append((gain / max(4.0, n.est_minutes), nid, kind))

    review_pool = list(ctx.review_due)
    review_cap = max(1, int(budget / 45 * 1))  # ~1 item ≈ ≤20% of 45 min

    # exploit arm: gain/cost descending, cluster interleaving ≤2 consecutive
    cands.sort(key=lambda t: (-t[0], t[1]))
    cluster_run: dict[str, int] = {}
    exploit: list[tuple[str, str]] = []
    for gain, nid, kind in cands:
        if len(exploit) >= MIN_ITEMS:
            break
        n = ctx.nodes[nid]
        if cluster_run.get(n.topic, 0) >= 2:
            continue
        exploit.append((nid, kind))
        cluster_run[n.topic] = cluster_run.get(n.topic, 0) + 1

    # exploration arm (bandit): swap in one random learnable node
    explore_pick: tuple[str, str] | None = None
    pool = [nid for _gain, nid, _kind in cands if nid not in {e[0] for e in exploit}]
    if pool:
        pick = rng.choice(sorted(pool))
        n = ctx.nodes[pick]
        kind = "lesson" if n.has_lesson else "practice"
        explore_pick = (pick, kind)

    # --- assemble ------------------------------------------------------------
    # exploitation items: propensity = (1 - EXPLORE_RATE) mass on argmax arm
    for nid, kind in exploit:
        n = ctx.nodes[nid]
        prop = (1.0 - EXPLORE_RATE) / max(1, len(exploit))
        reason = _exploit_reason(n, kind)
        items.append(Item(type=kind, node_id=nid, est_min=n.est_minutes, reason=reason,
                          propensity=prop, generator_id=(n.generators[0] if n.generators else None)))
        used.add(nid)

    if explore_pick and len(items) < MAX_ITEMS:
        nid, kind = explore_pick
        n = ctx.nodes[nid]
        items.append(Item(
            type=kind, node_id=nid, est_min=n.est_minutes,
            reason="Explore: sampled from the bandit slice so the plan doesn't go stale.",
            policy_id=POLICY_ID + "+explore",
            propensity=EXPLORE_RATE / max(1, len(pool)),
            generator_id=(n.generators[0] if n.generators else None),
        ))
        used.add(nid)

    # reviews (spaced repetition floor)
    for nid in review_pool:
        if len(items) >= MAX_ITEMS or sum(1 for i in items if i.type == "review") >= review_cap:
            break
        if nid in used:
            continue
        n = ctx.nodes[nid]
        items.append(Item(
            type="review", node_id=nid, est_min=max(5, n.est_minutes // 2),
            reason=f"Revive: retention slipped to {n.retention:.0%} since your last touch.",
            propensity=1.0,
            generator_id=(n.generators[0] if n.generators else None),
        ))
        used.add(nid)

    # repair items from recent mistakes (diagnose → plan loop)
    error_nodes = sorted((nid for nid in used | set(ctx.frontier) if ctx.nodes.get(nid) and ctx.nodes[nid].error_count > 0),
                         key=lambda x: -ctx.nodes[x].error_count)
    for nid in error_nodes:
        if len(items) >= MIN_ITEMS + 1 or len(items) >= MAX_ITEMS:
            break
        if nid in used:
            continue
        n = ctx.nodes[nid]
        if not n.generators and not n.has_lesson:
            continue
        items.append(Item(
            type="repair", node_id=nid, est_min=8,
            reason=f"Fix your recurring mistake: {n.error_count} wrong attempt(s) on this node.",
            propensity=1.0,
            generator_id=(n.generators[0] if n.generators else None),
        ))
        used.add(nid)

    # pad with top-up lessons from remediation/frontier
    for nid in sorted(set(ctx.remediation) | set(ctx.frontier)):
        if len(items) >= MIN_ITEMS:
            break
        if nid in used:
            continue
        n = ctx.nodes.get(nid)
        if not n or (not n.has_lesson and not n.generators):
            continue
        kind = "lesson" if n.has_lesson else "practice"
        items.append(Item(type=kind, node_id=nid, est_min=n.est_minutes,
                          reason="Next step on your skill tree.", propensity=1.0,
                          generator_id=(n.generators[0] if n.generators else None)))
        used.add(nid)

    log = {
        "policy_id": POLICY_ID,
        "seed": ctx.seed,
        "lens": ctx.lens_id,
        "frontier": sorted(ctx.frontier),
        "remediation": sorted(ctx.remediation),
        "review_due": sorted(ctx.review_due),
        "explore": explore_pick[0] if explore_pick else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return items[:MAX_ITEMS], log


def _exploit_reason(n: NodeInfo, kind: str) -> str:
    if kind == "lesson":
        return (f"Unlocks more of the tree: {n.topic} sits at {n.m_eff:.0%} mastery "
                f"and carries lens weight {n.weight:.1f}.")
    return (f"Verified practice on {n.topic}: {n.attempts} attempt(s) so far, "
            f"mastery {n.m_eff:.0%}.")
