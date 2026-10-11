"""API v1 surface: contracts, trust invariants, idempotency, privacy."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from edgen.api.app import create_app


@pytest.fixture()
def client(state):
    return TestClient(create_app(state))


def _problem(client, node_id, seed=1):
    r = client.get("/v1/problems", params={"node_id": node_id, "seed": seed})
    assert r.status_code == 200, r.text
    return r.json()


def _correct_value(state, node_id, instance_id):
    pool, _ = state.pool_for_node(node_id)
    answer, _ = pool.answer_key(instance_id)
    return answer.comparable


def test_health(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert body["nodes"] > 0
    assert body["generators"] == 5


def test_tracks_and_tree(client):
    tracks = client.get("/v1/tracks").json()
    assert tracks[0]["id"] == "gate_cse"
    tree = client.get("/v1/tree", params={"lens": "gate_cse"}).json()
    assert len(tree["order"]) == len(tree["nodes"]) > 0


def test_readiness_and_plan_for_new_user(client):
    assert client.get("/v1/readiness", params={"lens": "gate_cse"}).json()["readiness"] == 0.0
    plan = client.get("/v1/plan/today", params={"lens": "gate_cse"}).json()
    assert len(plan["items"]) >= 3


def test_problem_never_leaks_the_answer_key(client, state):
    p = _problem(client, "cs.os.cache_mapping")
    # Options are strings only; there is no correct flag on the wire.
    assert all(isinstance(o, str) for o in p["options"])
    assert p["badge"] == "VERIFIED"
    assert "correct" not in p


def test_attempt_grades_against_verified_key(client, state):
    node = "cs.os.cache_mapping"
    p = _problem(client, node)
    good = _correct_value(state, node, p["instance_id"])
    r = client.post(
        "/v1/attempts",
        json={
            "id": "a1", "user_id": "u1", "node_id": node,
            "instance_id": p["instance_id"], "response": good,
            "confidence": 75, "subject": "cs.os",
        },
    ).json()
    assert r["accepted"] is True
    assert r["correct"] is True
    assert r["badge"] == "VERIFIED"
    assert r["mastery_after"] > 0.15
    assert r["calibration"] is not None


def test_attempt_is_idempotent(client, state):
    node = "cs.os.cache_mapping"
    p = _problem(client, node)
    good = _correct_value(state, node, p["instance_id"])
    body = {"id": "same-id", "user_id": "u1", "node_id": node,
            "instance_id": p["instance_id"], "response": good}
    first = client.post("/v1/attempts", json=body).json()
    second = client.post("/v1/attempts", json=body).json()
    assert first["accepted"] is True
    assert second["accepted"] is False
    # The Twin did not double-count.
    assert second["mastery_after"] == first["mastery_after"]


def test_wrong_answer_returns_error_tag(client, state):
    node = "cs.os.cache_mapping"
    p = _problem(client, node)
    pool, _ = state.pool_for_node(node)
    _, distractors = pool.answer_key(p["instance_id"])
    if not distractors:
        pytest.skip("no distractors for this instance")
    r = client.post("/v1/attempts", json={
        "id": "wrong-1", "user_id": "u2", "node_id": node,
        "instance_id": p["instance_id"], "response": distractors[0].value,
    }).json()
    assert r["correct"] is False
    assert r["error_tag"] == distractors[0].error_tag


def test_attempt_on_unbacked_node_is_404(client):
    r = client.post("/v1/attempts", json={
        "id": "x", "user_id": "u", "node_id": "cs.os.scheduling.fcfs",
        "instance_id": "nope", "response": 0,
    })
    assert r.status_code == 404


def test_daily_drop_is_deterministic_per_day(client):
    a = client.get("/v1/daily-drop").json()
    b = client.get("/v1/daily-drop").json()
    assert a["instance_id"] == b["instance_id"]
    assert a["badge"] == "VERIFIED"


def test_daily_drop_answer_grid(client, state):
    drop = client.get("/v1/daily-drop").json()
    # Find the owning node, then the verified value.
    node = next(
        n for n in state.graph.lens_node_ids(state.lens)
        if (f := state.pool_for_node(n)) and drop["instance_id"] in f[0]._instances  # noqa: SLF001
    )
    good = _correct_value(state, node, drop["instance_id"])
    r = client.post("/v1/daily-drop/answer", json={"user_id": "u", "response": good}).json()
    assert r["correct"] is True
    assert r["grid"] == "\U0001f7e9"


def test_advisor_threshold(client):
    assert client.post("/v1/advisor", json={"question_type": "mcq", "calibrated_p": 0.3}).json()["recommend"] == "attempt"
    assert client.post("/v1/advisor", json={"question_type": "nat", "calibrated_p": 0.01}).json()["recommend"] == "attempt"
    assert client.post("/v1/advisor", json={"question_type": "bogus", "calibrated_p": 0.5}).status_code == 422


def test_seo_page_noindex_and_renders(client):
    r = client.get("/learn/cs.os.cache_mapping")
    assert r.status_code == 200
    assert "noindex" in r.text
    assert "VERIFIED" in r.text
    assert client.get("/learn/cs.os.nonexistent").status_code == 404


def test_privacy_export_and_delete(client, state):
    node = "cs.os.cache_mapping"
    p = _problem(client, node)
    good = _correct_value(state, node, p["instance_id"])
    client.post("/v1/attempts", json={"id": "pe1", "user_id": "priv", "node_id": node,
                                      "instance_id": p["instance_id"], "response": good})
    export = client.get("/v1/me/data", params={"user_id": "priv"}).json()["data"]
    assert len(export["attempts"]) == 1
    client.delete("/v1/me/data", params={"user_id": "priv"})
    after = client.get("/v1/me/data", params={"user_id": "priv"}).json()["data"]
    assert after["attempts"] == []


def test_admin_verification_all_verified(client):
    body = client.get("/v1/admin/verification").json()
    assert body["all_verified"] is True
    assert len(body["generators"]) == 5
