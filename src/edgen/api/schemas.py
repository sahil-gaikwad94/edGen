"""API request/response schemas (architecture §19)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrackOut(BaseModel):
    id: str
    title: str
    goal_type: str
    nodes: int


class NodeOut(BaseModel):
    id: str
    title: str
    prereqs: list[str]
    difficulty_prior: float
    est_minutes: dict[str, int]
    generators: list[str]
    has_lesson: bool


class TreeOut(BaseModel):
    lens: str
    order: list[str]
    nodes: dict[str, NodeOut]


class ReadinessOut(BaseModel):
    user_id: str
    lens: str
    readiness: float
    frontier: list[str]


class ProblemOut(BaseModel):
    """Client-safe problem: options never carry the correct flag."""

    node_id: str
    instance_id: str
    generator: str
    stem: str
    options: list[str]
    bucket: int
    badge: str


class AttemptIn(BaseModel):
    id: str = Field(..., description="Client-generated UUIDv7; makes the attempt idempotent")
    user_id: str
    node_id: str
    instance_id: str
    response: Any
    confidence: int | None = None
    hint_level: int = 0
    latency_ms: int | None = None
    policy_id: str | None = None
    propensity: float | None = None
    subject: str | None = None


class AttemptOut(BaseModel):
    id: str
    accepted: bool
    correct: bool
    answer: str
    error_tag: str | None
    badge: str
    mastery_after: float
    calibration: float | None = None


class DailyDropOut(BaseModel):
    track: str
    date: str
    stem: str
    options: list[str]
    instance_id: str
    badge: str


class DailyDropAnswerIn(BaseModel):
    user_id: str
    response: Any


class DailyDropResult(BaseModel):
    correct: bool
    grid: str
    answer: str


class AdvisorIn(BaseModel):
    question_type: str
    calibrated_p: float
    marks: int = 1
    all_options_known: bool = True


class AdvisorOut(BaseModel):
    recommend: str
    threshold: float
    expected_value: float
    reason: str


class DataExportOut(BaseModel):
    data: dict


class VerificationOut(BaseModel):
    generators: list[dict]
    all_verified: bool
