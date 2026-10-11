"""Planner data model."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Reason(StrEnum):
    FRONTIER = "frontier"       # new learning on the frontier
    REVIEW = "review"           # spaced review due (R < threshold)
    EXPLORE = "explore"         # bandit exploration slot
    MILESTONE = "milestone"     # role-lens milestone constraint


class PlanItem(BaseModel):
    node_id: str
    title: str
    reason: Reason
    minutes: int
    #: Expected weighted gain per minute (the sort key).
    gain_per_min: float
    #: Effective mastery before the item, for display ("from 34%").
    m_eff_before: float
    #: Whether this item is a Foundry/practice check.
    practice: bool = False
    #: Policy + propensity logged for offline evaluation (ADR #9).
    policy_id: str
    propensity: float = 1.0


class TodayPlan(BaseModel):
    user_id: str
    lens_id: str
    goal_type: str
    items: list[PlanItem] = Field(default_factory=list)
    total_minutes: int = 0
    #: Readiness under the lens before the plan runs.
    readiness_before: float = 0.0
    #: Expected readiness at the goal date if the plan is followed.
    expected_readiness_after: float = 0.0
    policy_id: str = "planner.v1"
