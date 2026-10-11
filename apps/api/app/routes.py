"""All /v1 routes (architecture §19 surface, W0/W1 subset)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from edgen_foundry import get_generator
from edgen_lesson_ir import LessonCore, lesson_to_html

from .content import get_content
from .db import dumps, loads, now_iso
from .model_gateway import cost_report
from .security import idempotent_response, store_idempotent
from .services import diagnostic_svc, drop_svc, judge_svc, lesson_svc, plan_svc, twin_svc
from .deps import ConnDep, UserDep, idempotency_key

router = APIRouter()


# --- health & metrics --------------------------------------------------------

@router.get("/healthz")
def healthz() -> dict:
    c = get_content()
    return {"ok": True, "graph_version": c.graph.version, "nodes": len(c.graph.nodes),
            "generators": judge_svc.published_ids()}


@router.get("/metrics/cost")
def metrics_cost(conn: ConnDep) -> dict:
    return cost_report(conn)


# --- session -----------------------------------------------------------------

@router.post("/session")
def create_session(conn: ConnDep, body: dict | None = None) -> dict:
    body = body or {}
    user_id = body.get("user_id") or str(uuid.uuid4())
    existing = conn.execute("select id from app_user where id=?", (user_id,)).fetchone()
    if existing is None:
        conn.execute(
            "insert into app_user (id, created_at, track, lens, goal_type, goal_date, minutes_per_day, onboarded, seed)"
            " values (?,?,?,?,?,?,?,?,?)",
            (user_id, now_iso(), body.get("track", "gate_cse"), body.get("lens", "gate_cse"),
             body.get("goal_type", "exam"), body.get("goal_date"),
             int(body.get("minutes_per_day", 45)), int(bool(body.get("onboarded"))),
             int(uuid.uuid4().int % 1_000_000)),
        )
        conn.commit()
    return {"user_id": user_id}


@router.patch("/session")
def update_session(conn: ConnDep, user: UserDep, body: dict) -> dict:
    fields = {k: v for k, v in body.items()
              if k in ("track", "lens", "goal_type", "goal_date", "minutes_per_day", "onboarded")}
    if "minutes_per_day" in fields:
        fields["minutes_per_day"] = int(fields["minutes_per_day"])
    if "onboarded" in fields:
        fields["onboarded"] = int(bool(fields["onboarded"]))
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"update app_user set {sets} where id=?", (*fields.values(), user))
        conn.commit()
    row = conn.execute("select * from app_user where id=?", (user,)).fetchone()
    if row is None:
        raise HTTPException(404, "unknown user")
    return dict(row)


# --- tracks & lenses ---------------------------------------------------------

@router.get("/tracks")
def tracks() -> dict:
    c = get_content()
    out = []
    for tid, t in c.tracks.items():
        lids = [lid for lid in t.get("lenses", []) if lid in c.lenses]
        node_count = 0
        for lid in lids:
            lens = c.lenses[lid]
            node_count = max(node_count, sum(1 for n in c.graph.nodes if lens.weight_of(n) > 0))
        out.append({
            **t,
            "lenses": lids,
            "graph_nodes": node_count,
            "syllabus": c.syllabus_summary(tid),
            "syllabus_available": True,
        })
    return {"tracks": out}


@router.get("/syllabi")
def syllabi() -> dict:
    c = get_content()
    return {"syllabi": [c.syllabus_summary(tid) for tid in c.tracks]}


@router.get("/syllabi/{track_id}")
def syllabus_detail(track_id: str) -> dict:
    c = get_content()
    syllabus = c.syllabi.get(track_id)
    if syllabus is None:
        raise HTTPException(404, "unknown track syllabus")
    return {**c.syllabus_summary(track_id),
            "scope_note": syllabus.get("scope_note"),
            "exam_structure": syllabus.get("exam_structure"),
            "phases": syllabus["phases"]}


@router.get("/lenses")
def lenses() -> dict:
    c = get_content()
    return {"lenses": [
        {"id": l.id, "goal_type": l.goal_type, "track": l.track, "title": l.title,
         "nodes": len(l.weighted_nodes)}
        for l in c.lenses.values()
    ]}


@router.get("/lenses/{lens_id}")
def lens_detail(lens_id: str) -> dict:
    c = get_content()
    lens = c.lenses.get(lens_id)
    if not lens:
        raise HTTPException(404, "unknown lens")
    top = sorted(lens.weights.items(), key=lambda kv: -kv[1])[:12]
    return {"id": lens.id, "goal_type": lens.goal_type, "track": lens.track,
            "title": lens.title, "config": lens.config, "milestones": lens.milestones,
            "node_count": len(lens.weighted_nodes),
            "top_weighted_nodes": [{"node_id": n, "weight": w} for n, w in top]}


# --- tree & readiness --------------------------------------------------------

@router.get("/tree")
def tree(conn: ConnDep, user: UserDep, lens: str = Query("gate_cse")) -> dict:
    c = get_content()
    if lens not in c.lenses:
        raise HTTPException(404, "unknown lens")
    mastery = twin_svc.mastery_of(conn, user)
    from edgen_twin import retention

    frontier = set(c.graph.frontier(mastery.__getitem__))
    remediation = set(c.graph.remediation(mastery.__getitem__))
    nodes_out: list[dict] = []
    for nid, n in c.graph.nodes.items():
        st = twin_svc.get_state(conn, user, nid, n.difficulty_prior)
        m = mastery.get(nid, n.difficulty_prior)
        r = retention(st.stability_days, st.last_seen_days) if st else 1.0
        if nid in frontier:
            state = "frontier"
        elif nid in remediation:
            state = "remediation"
        elif m >= 0.7:
            state = "mastered"
        else:
            state = "locked"
        nodes_out.append({
            "id": nid, "title": n.title, "subject": n.subject, "topic": n.topic,
            "prereqs": list(n.prereqs), "est_minutes": n.est_minutes,
            "generators": list(n.generators),
            "has_lesson": c.has_authored_lesson(nid),
            "misconceptions": len(n.misconceptions),
            "m_eff": round(m, 3), "retention": round(r, 3),
            "state": state,
            "review_due": state == "mastered" and r < 0.85,
            "attempts": st.attempts if st else 0,
        })
    rd = c.graph.readiness(c.lenses[lens], mastery.__getitem__)
    return {"lens": lens, "readiness": round(rd, 4) if rd is not None else None,
            "graph_version": c.graph.version,
            "counts": {s: sum(1 for v in nodes_out if v["state"] == s)
                       for s in ("frontier", "remediation", "mastered", "locked")},
            "nodes": nodes_out}


@router.get("/readiness")
def readiness(conn: ConnDep, user: UserDep, lens: str = Query("gate_cse")) -> dict:
    c = get_content()
    if lens not in c.lenses:
        raise HTTPException(404, "unknown lens")
    rd = plan_svc.readiness(conn, user, lens)
    return {"lens": lens, "readiness": round(rd, 4) if rd is not None else None,
            "goal_type": c.lenses[lens].goal_type}


# --- plan ---------------------------------------------------------------------

@router.get("/plan/today")
def plan_today(conn: ConnDep, user: UserDep, lens: str = Query("gate_cse"),
               refresh: bool = Query(False)) -> dict:
    if not refresh:
        plan = plan_svc.latest_plan(conn, user)
        if plan is not None:
            plan["readiness"] = plan_svc.readiness(conn, user, lens)
            return plan
    return plan_svc.generate_plan(conn, user, lens)


@router.post("/plan/refresh")
def plan_refresh(conn: ConnDep, user: UserDep, lens: str = Query("gate_cse")) -> dict:
    return plan_svc.generate_plan(conn, user, lens)


# --- lessons -------------------------------------------------------------------

@router.get("/lessons/{node_id}")
def lesson(conn: ConnDep, user: UserDep, node_id: str,
           lang: str = Query("en"), depth: str = Query("standard")) -> dict:
    return lesson_svc.get_lesson(conn, user, node_id, lang=lang, depth=depth)


@router.get("/lessons/{node_id}/html", include_in_schema=False)
def lesson_html(conn: ConnDep, user: UserDep, node_id: str, response: Response) -> str:
    """Server-rendered core for SEO/static pages (architecture §17)."""
    data = lesson_svc.get_lesson(conn, user, node_id)
    if data.get("status") != "ready":
        raise HTTPException(404, "lesson not available")
    core = LessonCore.model_validate(data["lesson"])
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    if core.review_status != "reviewed":
        response.headers["X-Robots-Tag"] = "noindex"  # thin content until reviewed
    return lesson_to_html(core)


# --- problems & judge ----------------------------------------------------------

@router.get("/problems/{generator_id}")
def problem(conn: ConnDep, user: UserDep, generator_id: str,
            bucket: int = Query(2, ge=1, le=5)) -> dict:
    try:
        return judge_svc.serve_instance(conn, generator_id, bucket, user_id=user)
    except judge_svc.UnknownGenerator:
        raise HTTPException(404, "unknown or unpublished generator")
    except judge_svc.NoInstance:
        raise HTTPException(503, "instance pool warming")


@router.post("/judge/jobs")
def judge_jobs(conn: ConnDep, body: dict, user: UserDep,
               key: Annotated[str | None, Depends(idempotency_key)]) -> dict:
    cached = idempotent_response(conn, user, key, "judge")
    if cached is not None:
        cached["idempotent_replay"] = True
        return cached
    if body.get("kind", "foundry") != "foundry":
        raise HTTPException(400, "only kind=foundry is available in W0")
    try:
        verdict = judge_svc.grade_submission(
            conn,
            generator_id=body["generator_id"],
            instance_id=body["instance_id"],
            submission=body.get("submission") or body.get("answer"),
            user_id=user,
            want_trace=bool(body.get("want_trace", True)),
        )
    except judge_svc.UnknownGenerator:
        raise HTTPException(404, "unknown generator")
    except judge_svc.NoInstance:
        raise HTTPException(404, "unknown instance")
    store_idempotent(conn, user, key, "judge", verdict)
    return verdict


# --- attempts (practice loop) ---------------------------------------------------

@router.post("/attempts")
def post_attempt(conn: ConnDep, body: dict, user: UserDep,
                 key: Annotated[str | None, Depends(idempotency_key)]) -> dict:
    cached = idempotent_response(conn, user, key, "attempt")
    if cached is not None:
        cached["idempotent_replay"] = True
        return cached

    generator_id = body.get("generator_id")
    instance_id = body.get("instance_id")
    answer = body.get("answer")
    confidence = body.get("confidence")
    hint_level = int(body.get("hint_level") or 0)
    steps = body.get("steps")
    policy_id = body.get("policy_id") or "client_direct_v1"
    propensity = float(body.get("propensity") or 1.0)

    if not generator_id or not instance_id:
        raise HTTPException(400, "generator_id and instance_id required")
    if confidence is not None and not (1 <= int(confidence) <= 100):
        raise HTTPException(400, "confidence must be 1..100")

    content = get_content()
    lens = body.get("lens") or "gate_cse"
    if lens not in content.lenses:
        raise HTTPException(400, f"unknown lens: {lens}")

    try:
        verdict = judge_svc.grade_submission(
            conn, generator_id=generator_id, instance_id=instance_id,
            submission=answer, user_id=user, want_trace=True,
        )
    except judge_svc.UnknownGenerator:
        raise HTTPException(404, "unknown generator")
    except judge_svc.NoInstance:
        raise HTTPException(404, "unknown instance")

    node_id = verdict["node_id"]
    node = content.graph.get(node_id)
    before, after = twin_svc.apply_attempt(
        conn, user_id=user, node_id=node_id, correct=bool(verdict["correct"]),
        confidence=int(confidence) if confidence is not None else None,
        hint_level=hint_level, error_tag=verdict.get("error_tag"),
        policy_id=policy_id, propensity=propensity, p_init=node.difficulty_prior,
    )
    import uuid as _uuid
    twin_svc.record_attempt(
        conn, attempt_id=str(_uuid.uuid4()), user_id=user, node_id=node_id,
        instance_id=instance_id, judge_job_id=verdict["judge_job_id"],
        generator_id=generator_id, correct=bool(verdict["correct"]),
        confidence=int(confidence) if confidence is not None else None,
        hint_level=hint_level, latency_ms=body.get("latency_ms"),
        error_tag=verdict.get("error_tag"), steps=steps,
        policy_id=policy_id, propensity=propensity,
    )

    # Reasoning-Diff: typed steps aligned against the oracle trace
    divergence = None
    if steps:
        divergence = lesson_svc.reasoning_diff(list(steps), verdict.get("trace") or [])

    # Plan re-optimises after every attempt using the learner's current lens.
    new_plan = plan_svc.generate_plan(conn, user, lens)

    response = {
        "verdict": verdict,
        "mastery": {
            "node_id": node_id,
            "p_known_before": round(before.p_known, 4),
            "p_known_after": round(after.p_known, 4),
            "m_eff_after": round(after.m_eff_now, 4),
            "error_tags": after.error_tags,
        },
        "reasoning_diff": divergence,
        "plan": new_plan,
        "policy_id": policy_id,
        "propensity": propensity,
    }
    store_idempotent(conn, user, key, "attempt", response)
    return response


# --- placement diagnostic --------------------------------------------------------

@router.post("/diagnostic/start")
def diagnostic_start(conn: ConnDep, user: UserDep,
                     key: Annotated[str | None, Depends(idempotency_key)]) -> dict:
    cached = idempotent_response(conn, user, key, "diag_start")
    if cached is not None:
        return cached
    out = diagnostic_svc.start(conn, user)
    store_idempotent(conn, user, key, "diag_start", out)
    return out


@router.get("/diagnostic")
def diagnostic_get(conn: ConnDep, user: UserDep) -> dict:
    state = diagnostic_svc.current(conn, user)
    if state is None:
        raise HTTPException(404, "no diagnostic started")
    return state


@router.post("/diagnostic/answer")
def diagnostic_answer(conn: ConnDep, body: dict, user: UserDep) -> dict:
    out = diagnostic_svc.answer(
        conn, user,
        idx=int(body.get("idx", -1)),
        submission=body.get("answer"),
        confidence=body.get("confidence"),
        hint_level=int(body.get("hint_level") or 0),
    )
    if "error" in out:
        status = 409 if out["error"] in ("out_of_order", "already_complete") else 404
        raise HTTPException(status_code=status, detail=out)
    if out.get("status") == "complete":
        out["plan"] = plan_svc.generate_plan(conn, user, "gate_cse")
    return out


# --- daily drop ------------------------------------------------------------------

@router.get("/daily-drop")
def daily_drop(conn: ConnDep, user: UserDep, track: str = Query("gate_cse")) -> dict:
    return drop_svc.drop_payload(conn, user, track)


@router.post("/daily-drop/answer")
def daily_drop_answer(conn: ConnDep, body: dict, user: UserDep) -> dict:
    return drop_svc.submit_drop(
        conn, user, answer=body.get("answer"),
        confidence=body.get("confidence"), track=body.get("track", "gate_cse"),
    )


@router.get("/daily-drop/history")
def daily_drop_history(conn: ConnDep, user: UserDep, track: str = Query("gate_cse")) -> dict:
    return drop_svc.history(conn, user, track)


# --- runs (agent event log, architecture §5) ------------------------------------

@router.post("/runs")
def create_run(conn: ConnDep, body: dict, user: UserDep) -> dict:
    kind = body.get("kind", "core_generation")
    run_id = str(uuid.uuid4())
    node_id = body.get("node_id")
    c = get_content()
    events: list[tuple[str, str, dict]] = [
        ("CREATED", "orchestrator", {"kind": kind, "node_id": node_id}),
        ("PLANNED", "orchestrator", {"agents": ["explainer", "verifier"]}),
    ]
    authored = bool(node_id and c.has_authored_lesson(node_id))
    if kind == "core_generation" and authored:
        events += [
            ("RUNNING", "explainer", {"cache_hit": True}),
            ("VERIFYING", "verifier", {"receipts": "validated"}),
            ("READY", "orchestrator", {"served": "authored_core"}),
        ]
        status = "READY"
        payload = {"provenance": "authored", "cache_hit": True, "node_id": node_id}
    elif kind == "core_generation":
        events.append(("QUEUED", "explainer", {"reason": "long-tail core pending batch authoring"}))
        status = "QUEUED"
        payload = {"status": "queued", "node_id": node_id,
                   "note": "queued for offline generation + human review (architecture §6)"}
    else:
        events.append(("FAILED", "orchestrator", {"reason": "unknown run kind"}))
        status = "FAILED"
        payload = {"error": "unknown run kind"}
    conn.execute("insert into run (id, kind, user_id, status, payload, created_at, updated_at)"
                 " values (?,?,?,?,?,?,?)",
                 (run_id, kind, user, status, dumps(payload), now_iso(), now_iso()))
    for i, (etype, agent, epayload) in enumerate(events):
        conn.execute("insert into run_events (run_id, seq, ts, type, agent, payload) values (?,?,?,?,?,?)",
                     (run_id, i, now_iso(), etype, agent, dumps(epayload)))
    conn.commit()
    return {"run_id": run_id, "status": status, "payload": payload,
            "events": [{"seq": i, "type": t, "agent": a} for i, (t, a, _) in enumerate(events)]}


@router.get("/runs/{run_id}")
def get_run(conn: ConnDep, run_id: str) -> dict:
    row = conn.execute("select * from run where id=?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "unknown run")
    events = [dict(r) for r in conn.execute(
        "select seq, ts, type, agent, payload from run_events where run_id=? order by seq", (run_id,))]
    for e in events:
        e["payload"] = loads(e["payload"], {})
    return {"run_id": run_id, "kind": row["kind"], "status": row["status"],
            "payload": loads(row["payload"], {}), "events": events}


# --- me / privacy (export + delete, W1 must-have) ---------------------------------

@router.get("/me/data")
def export_data(conn: ConnDep, user: UserDep) -> dict:
    return twin_svc.export_user(conn, user)


@router.delete("/me/data")
def delete_data(conn: ConnDep, user: UserDep) -> dict:
    n = twin_svc.delete_user(conn, user)
    return {"deleted": n, "user_id": user}


@router.get("/me/calibration")
def calibration(conn: ConnDep, user: UserDep) -> dict:
    return twin_svc.calibration(conn, user)
