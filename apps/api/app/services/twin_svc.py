"""Twin service: persistence around the pure edgen_twin model (architecture §7).

Rules:
* Every personalization decision stores policy_id + propensity (ADR 9).
* The Twin is always rebuildable from `attempt`.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from edgen_twin import BKTParams, TwinState, brier_score, conf_bin, reliability_curve

from ..db import dumps, loads, now_iso


def get_state(conn: sqlite3.Connection, user_id: str, node_id: str, p_init: float) -> TwinState | None:
    row = conn.execute(
        "select * from twin_state where user_id=? and node_id=?", (user_id, node_id)
    ).fetchone()
    if row is None:
        return None
    return TwinState(
        user_id=user_id,
        node_id=node_id,
        p_known=row["p_known"],
        stability_days=row["stability_days"],
        last_seen_days=row["last_seen_days"],
        attempts=row["attempts"],
        error_tags=loads(row["error_tags"], {}),
    )


def p_known_or_prior(conn: sqlite3.Connection, user_id: str, node_id: str, prior: float) -> float:
    st = get_state(conn, user_id, node_id, prior)
    return st.p_known if st else prior


def mastery_of(conn: sqlite3.Connection, user_id: str) -> dict[str, float]:
    """m_eff per node: p_known × R(now) — nodes without state use their prior
    (last_seen=0 ⇒ R=1, so m_eff = prior)."""
    from ..content import get_content

    content = get_content()
    priors = {nid: n.difficulty_prior for nid, n in content.graph.nodes.items()}
    m: dict[str, float] = dict(priors)
    for row in conn.execute("select * from twin_state where user_id=?", (user_id,)):
        st = TwinState(
            user_id=user_id, node_id=row["node_id"], p_known=row["p_known"],
            stability_days=row["stability_days"], last_seen_days=row["last_seen_days"],
            attempts=row["attempts"], error_tags=loads(row["error_tags"], {}),
        )
        m[st.node_id] = st.m_eff_now
    return m


def apply_attempt(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    node_id: str,
    correct: bool,
    confidence: int | None,
    hint_level: int = 0,
    error_tag: str | None = None,
    policy_id: str,
    propensity: float,
    p_init: float,
) -> tuple[TwinState, TwinState]:
    """Apply one attempt; returns (before, after)."""
    before = get_state(conn, user_id, node_id, p_init) or TwinState(
        user_id=user_id, node_id=node_id, p_known=p_init
    )
    after = before.apply_attempt(
        correct, params=BKTParams(), hint_level=hint_level or 0, error_tag=error_tag
    )
    conn.execute(
        "insert into twin_state (user_id, node_id, p_known, stability_days, last_seen_days, attempts, error_tags)"
        " values (?,?,?,?,?,?,?)"
        " on conflict(user_id, node_id) do update set p_known=excluded.p_known,"
        " stability_days=excluded.stability_days, last_seen_days=excluded.last_seen_days,"
        " attempts=excluded.attempts, error_tags=excluded.error_tags",
        (user_id, node_id, after.p_known, after.stability_days, after.last_seen_days,
         after.attempts, dumps(after.error_tags)),
    )
    # calibration bins (confidence → outcome)
    if confidence is not None:
        b = conf_bin(confidence)
        correct_n = 1 if correct else 0
        conn.execute(
            "insert into calibration_bin (user_id, conf_bin, n, n_correct) values (?,?,1,?)"
            " on conflict(user_id, conf_bin) do update set n=n+1, n_correct=n_correct+excluded.n_correct",
            (user_id, b, correct_n),
        )
    conn.commit()
    return before, after


def record_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: str,
    user_id: str,
    node_id: str | None,
    instance_id: str | None,
    judge_job_id: str | None,
    generator_id: str | None,
    correct: bool,
    confidence: int | None,
    hint_level: int,
    latency_ms: int | None,
    error_tag: str | None,
    steps: list[str] | None,
    policy_id: str,
    propensity: float,
) -> None:
    conn.execute(
        "insert into attempt (id, user_id, node_id, instance_id, judge_job_id, generator_id, correct,"
        " confidence, hint_level, latency_ms, error_tag, steps, policy_id, propensity, ts)"
        " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (attempt_id, user_id, node_id, instance_id, judge_job_id, generator_id, int(correct),
         confidence, hint_level, latency_ms, error_tag, dumps(steps) if steps else None,
         policy_id, propensity, now_iso()),
    )
    conn.commit()


def calibration(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    bins = {r["conf_bin"]: (r["n"], r["n_correct"]) for r in conn.execute(
        "select conf_bin, n, n_correct from calibration_bin where user_id=?", (user_id,))}
    outcomes: list[tuple[int, int]] = []
    for r in conn.execute("select confidence, correct from attempt where user_id=? and confidence is not null", (user_id,)):
        outcomes.append((r["confidence"], r["correct"]))
    return {
        "reliability": reliability_curve(bins),
        "brier": brier_score(outcomes),
        "n": len(outcomes),
    }


def export_user(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {"user_id": user_id}
    for table, col in [("twin_state", "user_id"), ("attempt", "user_id"),
                       ("calibration_bin", "user_id"), ("plan_event", "user_id"),
                       ("daily_drop_attempt", "user_id"), ("diagnostic_state", "user_id")]:
        out[table] = [dict(r) for r in conn.execute(f"select * from {table} where {col}=?", (user_id,))]
    u = conn.execute("select * from app_user where id=?", (user_id,)).fetchone()
    out["app_user"] = dict(u) if u else None
    return out


def delete_user(conn: sqlite3.Connection, user_id: str) -> int:
    deleted = 0
    for table in ["twin_state", "attempt", "calibration_bin", "plan_event",
                  "daily_drop_attempt", "diagnostic_state", "idempotency", "judge_job", "run"]:
        cur = conn.execute(f"delete from {table} where user_id=?", (user_id,))
        deleted += cur.rowcount
    conn.execute("delete from run_events where run_id in (select id from run where user_id=?)", (user_id,))
    conn.execute("delete from app_user where id=?", (user_id,))
    conn.commit()
    return deleted
