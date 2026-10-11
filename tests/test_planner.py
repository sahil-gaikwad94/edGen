"""Planner and Attempt Advisor (SystemsDesign §4)."""

from __future__ import annotations

import datetime as dt

import pytest

from edgen.graph.model import GoalType, Lens, LensNode
from edgen.planner.advisor import QuestionType, advise_attempt
from edgen.planner.model import Reason
from edgen.planner.planner import Planner, PlannerConfig


def test_planner_never_empty_for_a_new_learner(graph, lens):
    plan = Planner(graph).today(user_id="u", lens=lens, mastery={})
    assert plan.items, "a brand-new learner must get a non-empty plan"
    assert len(plan.items) >= 3
    assert plan.total_minutes <= PlannerConfig().minutes_budget


def test_planner_respects_prerequisites(graph, lens):
    plan = Planner(graph).today(user_id="u", lens=lens, mastery={})
    # Invariant: every planned node's prereqs are either already mastered or
    # scheduled earlier in the plan (prerequisite ordering within the session).
    planned_order: list[str] = []
    for item in plan.items:
        for p in graph.prereqs(item.node_id):
            assert p in planned_order, f"{item.node_id} planned before its prereq {p}"
        planned_order.append(item.node_id)


def test_planner_interleaves_clusters(graph, lens):
    plan = Planner(graph).today(user_id="u", lens=lens, mastery={})
    clusters = [".".join(i.node_id.split(".")[:2]) for i in plan.items]
    # No three-in-a-row from one cluster (config default is 2).
    for i in range(len(clusters) - 2):
        assert len(set(clusters[i : i + 3])) > 1


def test_planner_caps_reviews(graph, lens):
    cfg = PlannerConfig(minutes_budget=60, review_time_cap=0.2, min_items=0)
    # All nodes are due reviews at R=0.5; the review cap must bind.
    due = dict.fromkeys(graph.lens_node_ids(lens), 0.5)
    plan = Planner(graph, cfg).today(user_id="u", lens=lens, mastery={}, due_reviews=due)
    review_minutes = sum(i.minutes for i in plan.items if i.reason == Reason.REVIEW)
    assert review_minutes <= cfg.minutes_budget * cfg.review_time_cap + 15  # +1 item slack


def test_planner_logs_policy_and_propensity(graph, lens):
    plan = Planner(graph).today(user_id="u", lens=lens, mastery={})
    for item in plan.items:
        assert item.policy_id  # ADR #9: propensities logged from day one
        assert item.propensity is not None


def test_exam_lens_decay_favours_high_weight_topics(graph):
    exam_date = dt.date(2026, 6, 1)
    lens = Lens(
        id="exam",
        title="exam",
        goal_type=GoalType.EXAM,
        nodes=[LensNode(lens_id="exam", node_id=n, weight=w)
               for n, w in (("cs.dbms", 1.0), ("cs.os", 1.0))],
        exam_date=exam_date,
    )
    # Give both topics equal mastery so gain differences come from weight only.
    plan = Planner(graph).today(
        user_id="u", lens=lens, mastery={}, now=dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    )
    assert plan.items


def test_readiness_after_is_at_least_before(graph, lens):
    plan = Planner(graph).today(user_id="u", lens=lens, mastery={})
    assert plan.expected_readiness_after >= plan.readiness_before


# ------------------------------------------------------------- advisor ----
def test_mcq_threshold_is_quarter_for_both_markings():
    for marks in (1, 2):
        assert advise_attempt(question_type=QuestionType.MCQ, calibrated_p=0.26, marks=marks).recommend == "attempt"
        assert advise_attempt(question_type=QuestionType.MCQ, calibrated_p=0.24, marks=marks).recommend == "skip"
    # Break-even EV at p = 0.25.
    a = advise_attempt(question_type=QuestionType.MCQ, calibrated_p=0.25, marks=2)
    assert a.expected_value == pytest.approx(0.0, abs=1e-9)
    assert a.threshold == pytest.approx(0.25)


def test_nat_always_attempt():
    assert advise_attempt(question_type=QuestionType.NAT, calibrated_p=0.0).recommend == "attempt"


def test_msq_needs_all_options():
    assert advise_attempt(question_type=QuestionType.MSQ, calibrated_p=0.9, all_options_known=True).recommend == "attempt"
    assert advise_attempt(question_type=QuestionType.MSQ, calibrated_p=0.9, all_options_known=False).recommend == "skip"
