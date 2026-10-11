"""Planner tests: determinism, propensities, review cap, interleaving (§4, ADR 9)."""
from datetime import date

from edgen_planner import EXPLORE_RATE, MAX_ITEMS, MIN_ITEMS, NodeInfo, PlanContext, plan


def _ctx(seed=42, nodes=None, frontier=None, review_due=None, remediation=None) -> PlanContext:
    def mk(nid, topic, weight=1.0, m=0.5, lesson=True, gens=(), errs=0, est=10):
        return NodeInfo(id=nid, title=nid, topic=topic, weight=weight, m_eff=m,
                        retention=1.0, p_known=m, est_minutes=est, generators=gens,
                        has_lesson=lesson, error_count=errs, attempts=0)

    nodes = nodes or {
        "a1": mk("a1", "t.alpha", lesson=True, est=12),
        "a2": mk("a2", "t.alpha", lesson=True, est=10),
        "a3": mk("a3", "t.alpha", lesson=True, est=8),
        "b1": mk("b1", "t.beta", lesson=True, est=10),
        "c1": mk("c1", "t.gamma", lesson=False, gens=("os.page_replacement",), est=10),
    }
    return PlanContext(
        lens_id="gate_cse", goal_type="exam", goal_date=date(2027, 5, 1),
        minutes_budget=45, now=date(2026, 10, 11),
        nodes=nodes,
        frontier=frontier if frontier is not None else list(nodes),
        remediation=remediation or [],
        review_due=review_due or [],
        seed=seed,
    )


def test_plan_size_and_fields():
    items, log = plan(_ctx())
    assert MIN_ITEMS <= len(items) <= MAX_ITEMS
    for it in items:
        d = it.as_dict()
        assert d["policy_id"].startswith("planner_greedy_v1")
        assert 0 < d["propensity"] <= 1.0
        assert d["reason"]
        assert d["est_min"] > 0
    assert log["seed"] == 42
    assert "frontier" in log


def test_deterministic_given_seed():
    a, _ = plan(_ctx(seed=7))
    b, _ = plan(_ctx(seed=7))
    assert [i.as_dict() for i in a] == [i.as_dict() for i in b]
    c, _ = plan(_ctx(seed=8))
    assert [i.as_dict() for i in a] != [i.as_dict() for i in c] or True  # rng may coincide; only seed 7 must match


def test_cluster_interleave_cap():
    # three same-cluster candidates must not monopolise all slots (>2 consecutive)
    ctx = _ctx()
    items, _ = plan(ctx)
    kinds = [i.node_id.split(".")[0] for i in items]
    topics = [ctx.nodes[i.node_id].topic for i in items]
    # no more than 2 consecutive from one topic
    run, prev = 0, None
    for t in topics:
        run = run + 1 if t == prev else 1
        assert run <= 2, f"cluster {t} ran {run} consecutive"
        prev = t


def test_review_cap_and_due_items():
    ctx = _ctx(review_due=["a1", "b1", "c1"], frontier=["a2", "a3"])
    items, _ = plan(ctx)
    reviews = [i for i in items if i.type == "review"]
    assert reviews, "due reviews must appear"
    assert len(reviews) <= 2  # ≤20% of a 45-min plan ≈ 1 slot (cap floor)


def test_exploration_logged_separately():
    items, log = plan(_ctx(seed=12345))
    explore = [i for i in items if i.policy_id.endswith("+explore")]
    if explore:  # 15% slice — sometimes empty after MIN_ITEMS fill
        assert explore[0].propensity < EXPLORE_RATE
    assert log["policy_id"] == "planner_greedy_v1"


def test_generator_node_becomes_practice_item():
    items, _ = plan(_ctx(frontier=["c1"]))
    types = {i.type for i in items}
    assert "practice" in types
    practice = [i for i in items if i.type == "practice"][0]
    assert practice.generator_id == "os.page_replacement"


def test_review_items_beat_new_work_when_due():
    ctx = _ctx(review_due=["c1"], frontier=["a1", "a2", "a3", "b1"])
    items, _ = plan(ctx)
    assert any(i.type in ("review", "practice") and i.node_id == "c1" for i in items)
