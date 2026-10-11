"""Planner service: build PlanContext from the graph + Twin, persist plans."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from edgen_planner import PlanContext, NodeInfo, plan as run_plan

from ..content import get_content
from ..db import dumps, loads, now_iso
from . import twin_svc


def _day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def build_context(conn: sqlite3.Connection, user_id: str, lens_id: str) -> PlanContext:
    content = get_content()
    graph = content.graph
    lens = content.lenses[lens_id]
    mastery = twin_svc.mastery_of(conn, user_id)
    error_counts = _error_counts(conn, user_id)

    nodes: dict[str, NodeInfo] = {}
    for nid, n in graph.nodes.items():
        st = twin_svc.get_state(conn, user_id, nid, n.difficulty_prior)
        from edgen_twin import retention
        m = mastery.get(nid, n.difficulty_prior)
        r = retention(st.stability_days, st.last_seen_days) if st else 1.0
        nodes[nid] = NodeInfo(
            id=nid, title=n.title, topic=n.topic, weight=lens.weight_of(nid),
            m_eff=m, retention=r, p_known=(st.p_known if st else n.difficulty_prior),
            est_minutes=n.est_minutes, prereqs=n.prereqs, generators=n.generators,
            has_lesson=content.has_authored_lesson(nid),
            error_count=error_counts.get(nid, 0),
            attempts=(st.attempts if st else 0),
        )

    frontier = graph.frontier(mastery.__getitem__)
    remediation = graph.remediation(mastery.__getitem__)
    review_due = sorted(
        nid for nid, info in nodes.items()
        if info.p_known >= 0.7 and info.retention < 0.85
    )

    user = conn.execute("select * from app_user where id=?", (user_id,)).fetchone()
    goal_date = date.fromisoformat(user["goal_date"]) if user and user["goal_date"] else None
    seed_base = (user["seed"] if user else 0)
    today = datetime.now(timezone.utc).date()
    seed = seed_base * 1000 + today.toordinal()

    return PlanContext(
        lens_id=lens_id,
        goal_type=lens.goal_type,
        goal_date=goal_date,
        minutes_budget=(user["minutes_per_day"] if user and user["minutes_per_day"] else 45),
        now=today,
        nodes=nodes,
        frontier=frontier,
        remediation=remediation,
        review_due=review_due,
        seed=seed,
    )


def generate_plan(conn: sqlite3.Connection, user_id: str, lens_id: str) -> dict[str, Any]:
    ctx = build_context(conn, user_id, lens_id)
    items, log = run_plan(ctx)
    conn.execute(
        "insert into plan_event (user_id, ts, day, seed, policy_id, items, log) values (?,?,?,?,?,?,?)",
        (user_id, now_iso(), _day(), ctx.seed, log["policy_id"],
         dumps([i.as_dict() for i in items]), dumps(log)),
    )
    conn.commit()
    return plan_response(items, log)


def plan_response(items, log: dict) -> dict[str, Any]:
    return {
        "day": _day(),
        "items": [i.as_dict() for i in items],
        "log": log,
        "total_minutes": sum(i.est_min for i in items),
    }


def latest_plan(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "select * from plan_event where user_id=? order by id desc limit 1", (user_id,)
    ).fetchone()
    if row is None or row["day"] != _day():
        return None
    return {
        "day": row["day"],
        "items": loads(row["items"], []),
        "log": loads(row["log"], {}),
        "total_minutes": sum(i.get("est_min", 0) for i in loads(row["items"], [])),
    }


def _error_counts(conn: sqlite3.Connection, user_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in conn.execute(
        "select node_id, count(*) c from attempt where user_id=? and correct=0 and node_id is not null"
        " group by node_id", (user_id,),
    ):
        out[r["node_id"]] = r["c"]
    return out


def readiness(conn: sqlite3.Connection, user_id: str, lens_id: str) -> float | None:
    content = get_content()
    lens = content.lenses[lens_id]
    mastery = twin_svc.mastery_of(conn, user_id)
    return content.graph.readiness(lens, mastery.__getitem__)
