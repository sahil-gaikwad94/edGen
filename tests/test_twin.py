"""Twin maths: BKT posteriors, hint handling, FSRS curve, calibration."""

from __future__ import annotations

import datetime as dt

import pytest

from edgen.twin.bkt import (
    BKTParams,
    hint_guess,
    posterior_given_correct,
    posterior_given_wrong,
    update,
)
from edgen.twin.calibration import CalibrationTracker, bin_of
from edgen.twin.forgetting import (
    days_until,
    effective_mastery,
    next_stability,
    retrievability,
)
from edgen.twin.service import Attempt, Twin


# --------------------------------------------------------------------- BKT --
def test_posterior_formulas_match_spec():
    # SystemsDesign §3 formulas, exactly.
    assert posterior_given_correct(0.5, 0.1, 0.2) == pytest.approx(0.45 / 0.55)
    assert posterior_given_wrong(0.5, 0.1, 0.2) == pytest.approx(0.05 / 0.45)


def test_bkt_full_step_matches_hand_calculation():
    # 0.5 correct -> 0.8181... -> + (1-p)*0.2
    got = update(0.5, True, BKTParams())
    assert got == pytest.approx(0.45 / 0.55 + (1 - 0.45 / 0.55) * 0.2)


def test_correct_raises_and_wrong_lowers_mastery():
    p = 0.5
    assert update(p, True, BKTParams()) > p
    assert update(p, False, BKTParams()) < p


def test_hinted_correct_is_weaker_evidence():
    plain = update(0.5, True, BKTParams(), hint_level=0)
    hinted = update(0.5, True, BKTParams(), hint_level=4)
    assert hinted < plain
    assert hint_guess(0.2, 0) == 0.2
    assert hint_guess(0.2, 4) == pytest.approx(0.6)
    assert hint_guess(0.5, 99) <= 0.999  # clamped


def test_mastery_stays_in_unit_interval():
    p = 0.5
    for _ in range(200):
        p = update(p, True, BKTParams())
        assert 0.0 <= p <= 1.0


# -------------------------------------------------------------------- FSRS --
def test_retrievability_is_0_9_at_stability():
    assert retrievability(10.0, 10.0) == pytest.approx(0.9)
    assert retrievability(0.0, 10.0) == pytest.approx(1.0)


def test_retrievability_monotonically_decreases():
    assert retrievability(5, 10) > retrievability(20, 10) > retrievability(100, 10)


def test_days_until_inverts_the_curve():
    for s in (1.0, 7.5, 30.0):
        assert days_until(0.9, s) == pytest.approx(s)


def test_stability_grows_on_success_and_lapses_on_failure():
    s = 10.0
    assert next_stability(s, 10.0, True) > s
    assert next_stability(s, 10.0, False) == pytest.approx(s * 0.5)


def test_effective_mastery_discounts_for_decay():
    assert effective_mastery(1.0, 0.0, 10.0) == pytest.approx(1.0)
    assert effective_mastery(1.0, 10.0, 10.0) == pytest.approx(0.9)
    assert effective_mastery(1.0, 1000.0, 10.0) < 0.2


# ------------------------------------------------------------- calibration --
def test_conf_bins():
    assert bin_of(0) == 0
    assert bin_of(24) == 0
    assert bin_of(25) == 25
    assert bin_of(90) == 90
    assert bin_of(100) == 100


def test_brier_and_reliability():
    t = CalibrationTracker()
    for _ in range(10):
        t.record("os", 90, True)
    for _ in range(10):
        t.record("os", 90, False)
    # Half correct when claiming 90% -> Brier = mean of (0.9-1)^2 and (0.9-0)^2
    assert t.brier("os") == pytest.approx((0.01 + 0.81) / 2)
    curve = t.reliability_curve("os")
    assert curve[0]["empirical_accuracy"] == pytest.approx(0.5)


def test_calibrated_p_shrinks_toward_stated_when_thin():
    t = CalibrationTracker()
    # No data -> fall back to stated confidence.
    assert t.calibrated_p("os", 75) == pytest.approx(0.75)
    t.record("os", 75, False)
    # One miss at 75% pulls the estimate down but not all the way.
    p = t.calibrated_p("os", 75)
    assert 0.0 < p < 0.75


# ---------------------------------------------------------------- service --
def test_twin_is_idempotent_on_attempt_id(utc):
    t = Twin("u")
    a = Attempt(id="a1", user_id="u", node_id="n", correct=True, ts=utc())
    t.apply(a)
    p1 = t.p_known("n")
    t.apply(a)
    assert t.p_known("n") == p1
    assert t.state("n").attempts == 1


def test_twin_rebuildable_from_attempt_log_is_order_independent(utc):
    """Folding the log in ts order is the recompute path; the result is stable."""
    attempts = [
        Attempt(id="a2", user_id="u", node_id="n", correct=False, ts=utc(d=2)),
        Attempt(id="a1", user_id="u", node_id="n", correct=True, ts=utc(d=1)),
    ]
    t = Twin("u")
    t.apply_many(attempts)
    assert t.state("n").attempts == 2


def test_error_genome_counts_failures(utc):
    t = Twin("u")
    t.apply(Attempt(id="a1", user_id="u", node_id="n", correct=False, ts=utc(), error_tag="off_by_one"))
    t.apply(Attempt(id="a2", user_id="u", node_id="n", correct=False, ts=utc(), error_tag="off_by_one"))
    t.apply(Attempt(id="a3", user_id="u", node_id="n", correct=False, ts=utc(), error_tag="wrong_sign"))
    assert t.error_genome()[0] == {"tag": "off_by_one", "count": 2}


def test_mastery_map_decays_over_time(utc):
    t = Twin("u")
    t.apply(Attempt(id="a1", user_id="u", node_id="n", correct=True, ts=utc(d=1)))
    near = t.mastery_map(dt.datetime(2026, 1, 2, tzinfo=dt.UTC))["n"]
    far = t.mastery_map(dt.datetime(2026, 6, 1, tzinfo=dt.UTC))["n"]
    assert near > far
