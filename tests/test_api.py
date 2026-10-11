"""End-to-end API tests: the core loop from ideaBrief §7."""
from edgen_foundry import get_generator
from apps.api.app.db import connect, loads


def _solve(generator_id: str, instance_id: str):
    """Compute the verified answer in its JSON-safe canonical form."""
    conn = connect()
    row = conn.execute("select params from instance_pool where instance_id=?", (instance_id,)).fetchone()
    conn.close()
    params = loads(row["params"])
    gen = get_generator(generator_id)
    return gen.answer_key(params, gen.solve_a(params))


def test_health_and_tracks(client):
    r = client.get("/v1/healthz")
    assert r.status_code == 200 and r.json()["ok"]
    r = client.get("/v1/tracks")
    tracks = {t["id"]: t for t in r.json()["tracks"]}
    assert tracks["gate_cse"]["status"] == "active"
    assert tracks["full_stack"]["status"] == "upcoming"
    assert tracks["gate_cse"]["graph_nodes"] >= 100


def test_requires_user_header(client):
    assert client.get("/v1/tree").status_code == 401


def test_full_loop(client, user):
    # 1. skill tree
    r = client.get("/v1/tree?lens=gate_cse", headers=user)
    tree = r.json()
    assert tree["counts"]["frontier"] >= 3
    assert tree["readiness"] and 0 < tree["readiness"] < 1

    # 2. today plan (≥3 items, each with propensity)
    r = client.get("/v1/plan/today", headers=user)
    plan = r.json()
    assert len(plan["items"]) >= 3
    for it in plan["items"]:
        assert it["propensity"] > 0 and it["policy_id"]

    # 3. lesson (authored core with receipts)
    r = client.get("/v1/lessons/dbms.norm.bcnf", headers=user)
    lesson = r.json()
    assert lesson["status"] == "ready" and lesson["provenance"] == "authored"
    badges = {b["badge"] for b in lesson["lesson"]["blocks"] if b.get("badge")}
    assert "VERIFIED" in badges and "SOURCED" in badges

    # 4. verified practice: solve a problem correctly
    r = client.get("/v1/problems/dbms.serializability?bucket=2", headers=user)
    p = r.json()
    answer = _solve(p["generator_id"], p["instance_id"])
    r = client.post(
        "/v1/attempts",
        json={"generator_id": p["generator_id"], "instance_id": p["instance_id"],
              "answer": answer, "confidence": 75,
              "policy_id": "planner_greedy_v1", "propensity": 0.28,
              "steps": ["build edges", "check cycle", "emit order"]},
        headers=user,
    )
    body = r.json()
    assert r.status_code == 200
    assert body["verdict"]["correct"] is True
    assert body["verdict"]["trust_label"] == "VERIFIED"
    assert body["mastery"]["p_known_after"] > body["mastery"]["p_known_before"]
    assert body["reasoning_diff"] is not None
    assert body["plan"]["items"], "plan re-optimises after every attempt"

    # 5. Twin persisted; export contains attempts
    r = client.get("/v1/me/data", headers=user)
    data = r.json()
    assert len(data["attempt"]) >= 1
    assert data["attempt"][0]["policy_id"] == "planner_greedy_v1"


def test_idempotency_key_replays(client, user):
    r = client.get("/v1/problems/os.cpu_scheduling", headers=user)
    p = r.json()
    headers = {**user, "Idempotency-Key": "idem-123"}
    payload = {"generator_id": p["generator_id"], "instance_id": p["instance_id"],
               "answer": 0, "confidence": 50}
    first = client.post("/v1/attempts", json=payload, headers=headers).json()
    second = client.post("/v1/attempts", json=payload, headers=headers).json()
    assert second.get("idempotent_replay") is True
    assert second["verdict"]["judge_job_id"] == first["verdict"]["judge_job_id"]


def test_diagnostic_flow_completes(client, user):
    r = client.post("/v1/diagnostic/start", headers=user)
    assert r.status_code == 200
    diag = r.json()
    assert diag["status"] == "in_progress" and diag["total"] == 8
    idx = 0
    while idx < diag["total"]:
        item = diag["items"][idx]
        answer = _solve(item["generator_id"], item["instance_id"])
        r = client.post("/v1/diagnostic/answer", json={
            "idx": idx, "answer": answer, "confidence": 60,
        }, headers=user)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["correct"] is True
        assert out["mastery"]["after"] >= out["mastery"]["before"]
        idx = out["idx"]
    assert out["status"] == "complete"
    assert out["plan"]["items"], "diagnostic completion produces a plan"


def test_daily_drop_is_shared_and_gradeable(client, user):
    r = client.get("/v1/daily-drop", headers=user)
    drop = r.json()
    answer = _solve(drop["generator_id"], drop["instance_id"])
    r = client.post("/v1/daily-drop/answer", json={"answer": answer, "confidence": 80}, headers=user)
    out = r.json()
    assert out["correct"] is True and out["attempts"] == 1
    hist = client.get("/v1/daily-drop/history", headers=user).json()
    assert hist["grid"][0]["mark"] == "🟩"  # solved on first try
    # second submit keeps the win, increments attempts → grid degrades to 🟡
    r = client.post("/v1/daily-drop/answer", json={"answer": 0, "confidence": 10}, headers=user)
    out2 = r.json()
    assert out2["correct"] is True and out2["attempts"] == 2
    hist = client.get("/v1/daily-drop/history", headers=user).json()
    assert hist["grid"][0]["mark"] == "🟡"
    assert "Daily Drop" in hist["share_text"]


def test_scaffold_lesson_and_run_queueing(client, user):
    r = client.get("/v1/lessons/os.scheduling.multilevel", headers=user)
    body = r.json()
    assert body["provenance"] == "scaffold" and body["lesson"]["review_status"] == "draft"
    r = client.post("/v1/runs", json={"kind": "core_generation", "node_id": "os.scheduling.multilevel"},
                    headers=user)
    assert r.json()["status"] == "QUEUED"
    run_id = r.json()["run_id"]
    r = client.get(f"/v1/runs/{run_id}")
    assert r.json()["events"][-1]["type"] == "QUEUED"


def test_delete_data_wipes_user(client, user):
    client.get("/v1/tree", headers=user)  # touch
    r = client.delete("/v1/me/data", headers=user)
    assert r.status_code == 200 and r.json()["deleted"] >= 0
    # session row gone → export returns empty
    data = client.get("/v1/me/data", headers=user)
    assert data.status_code == 200
    assert data.json()["attempt"] == []


def test_attempt_replans_with_requested_lens_and_rejects_unknown(client, user):
    p = client.get("/v1/problems/os.cpu_scheduling", headers=user).json()
    payload = {
        "generator_id": p["generator_id"], "instance_id": p["instance_id"],
        "answer": "not-the-answer", "confidence": 50, "lens": "ai",
    }
    r = client.post("/v1/attempts", json=payload, headers=user)
    assert r.status_code == 200
    assert r.json()["plan"]["log"]["lens"] == "ai"

    before = len(client.get("/v1/me/data", headers=user).json()["attempt"])
    payload["lens"] = "not-a-lens"
    r = client.post("/v1/attempts", json=payload, headers=user)
    assert r.status_code == 400
    after = len(client.get("/v1/me/data", headers=user).json()["attempt"])
    assert after == before, "invalid lens must be rejected before recording a judged attempt"


def test_cost_metering_visible(client, user):
    client.get("/v1/lessons/os.scheduling.rr", headers=user)  # cache hit log
    r = client.get("/v1/metrics/cost", headers=user)
    rep = r.json()
    assert rep["totals"]["calls"] >= 1
    features = {f["feature"] for f in rep["by_feature"]}
    assert "lesson_core" in features
