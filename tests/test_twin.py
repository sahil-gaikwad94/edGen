"""Twin model tests — BKT math and FSRS-style forgetting (SystemsDesign §3)."""
import math

from edgen_twin import (
    BKTParams,
    TwinState,
    bkt_step,
    brier_score,
    conf_bin,
    m_eff,
    reliability_curve,
    retention,
    review_stability,
)


def test_bkt_correct_increases():
    p0 = 0.5
    p1 = bkt_step(p0, correct=True)
    assert p1 > p0
    # textbook update: P(L|c) = .5*.9 / (.5*.9 + .5*.2) = .45/.55 ≈ .818; +learn
    expected = 0.45 / 0.55 + (1 - 0.45 / 0.55) * BKTParams().p_learn
    assert math.isclose(p1, expected, rel_tol=1e-9)


def test_bkt_wrong_decreases():
    p1 = bkt_step(0.5, correct=False)
    # P(L|w) = .5*.1 / (.5*.1 + .5*.8) = .05/.45 ≈ .111 (no learn term)
    assert math.isclose(p1, 0.05 / 0.45, rel_tol=1e-9)
    assert p1 < 0.5


def test_hints_inflate_guess():
    # hinted-correct is weaker evidence → lower posterior than unhinted
    unhinted = bkt_step(0.5, True, hint_level=0)
    hinted = bkt_step(0.5, True, hint_level=2)
    assert hinted < unhinted


def test_retention_anchor_points():
    # R = 0.9 exactly when Δt equals stability S
    assert math.isclose(retention(10.0, 10.0), 0.9, rel_tol=1e-9)
    assert retention(30.0, 0.0) == 1.0
    assert retention(30.0, 100.0) < retention(30.0, 10.0)


def test_m_eff_is_product():
    assert math.isclose(m_eff(0.8, 10.0, 10.0), 0.8 * 0.9, rel_tol=1e-9)


def test_stability_grows_on_success_shrinks_on_failure():
    up = review_stability(10.0, 9.0, success=True)
    down = review_stability(10.0, 9.0, success=False)
    assert up > 10.0
    assert down < 10.0


def test_twin_state_apply_attempt_and_error_tags():
    s = TwinState(user_id="u", node_id="n", p_known=0.5)
    s2 = s.apply_attempt(False, error_tag="tag_a")
    assert s2.p_known < s.p_known
    assert s2.error_tags == {"tag_a": 1}
    assert s2.attempts == 1
    # a correct answer on the same tag repairs it
    s3 = s2.apply_attempt(True, error_tag="tag_a")
    assert s3.error_tags.get("tag_a", 0) == 0
    assert s3.p_known > s2.p_known


def test_calibration():
    assert conf_bin(30) == 25
    assert conf_bin(80) == 75
    assert conf_bin(88) == 90
    assert brier_score([(50, 1), (50, 0)]) == 0.25
    assert brier_score([]) is None
    curve = reliability_curve({75: (4, 3), 25: (0, 0)})
    assert len(curve) == 1 and curve[0]["observed"] == 0.75
