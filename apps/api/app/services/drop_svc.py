"""Daily Drop: one shared puzzle per track per day (IdeaBrief §8, §7 growth)."""
from __future__ import annotations

import hashlib
import random
import sqlite3
from datetime import datetime, timezone
from typing import Any

from edgen_foundry import get_generator

from .. import config
from ..content import get_content
from ..db import dumps, loads, now_iso
from .judge_svc import published_ids, serve_instance


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _seed(track: str, day: str) -> int:
    return int(hashlib.sha256(f"{track}:{day}".encode()).hexdigest(), 16)


def ensure_drop(conn: sqlite3.Connection, track: str = "gate_cse") -> dict[str, Any]:
    day = _today()
    row = conn.execute("select * from daily_drop where track=? and day=?", (track, day)).fetchone()
    if row:
        return dict(row)
    seed = _seed(track, day)
    gens = published_ids()
    gen_id = gens[seed % len(gens)]
    bucket = 3
    # deterministic instance from the pool
    reg = get_content().published_generators[gen_id]
    rows = conn.execute(
        "select instance_id, params from instance_pool where generator_id=? and version=? and bucket=? order by instance_id",
        (gen_id, int(reg.get("version", 1)), bucket),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"pool empty for {gen_id} bucket {bucket}")
    pick = rows[seed % len(rows)]
    gen = get_generator(gen_id)
    params = loads(pick["params"])
    answer_hash = hashlib.sha256(
        (gen.answer_key(params, gen.solve_a(params)) + config.VERDICT_SECRET).encode()
    ).hexdigest()
    conn.execute(
        "insert or ignore into daily_drop (track, day, generator_id, instance_id, answer_hash) values (?,?,?,?,?)",
        (track, day, gen_id, pick["instance_id"], answer_hash),
    )
    conn.commit()
    return dict(conn.execute("select * from daily_drop where track=? and day=?", (track, day)).fetchone())


def drop_payload(conn: sqlite3.Connection, user_id: str, track: str = "gate_cse") -> dict[str, Any]:
    row = ensure_drop(conn, track)
    gen = get_generator(row["generator_id"])
    params = loads(conn.execute(
        "select params from instance_pool where instance_id=?", (row["instance_id"],)).fetchone()["params"])
    attempt = conn.execute(
        "select * from daily_drop_attempt where user_id=? and day=? and track=?",
        (user_id, row["day"], track),
    ).fetchone()
    return {
        "track": track,
        "day": row["day"],
        "generator_id": row["generator_id"],
        "instance_id": row["instance_id"],
        "statement": gen.statement(params),
        "input_spec": gen.input_spec,
        "your_attempt": dict(attempt) if attempt else None,
        "streak_note": "Same problem for everyone today — spoilers stay out of the share grid.",
    }


def submit_drop(conn: sqlite3.Connection, user_id: str, answer: Any,
                confidence: int | None = None, track: str = "gate_cse") -> dict[str, Any]:
    from .judge_svc import grade_submission

    row = ensure_drop(conn, track)
    existing = conn.execute(
        "select * from daily_drop_attempt where user_id=? and day=? and track=?",
        (user_id, row["day"], track),
    ).fetchone()
    attempts = (existing["attempts"] if existing else 0) + 1
    verdict = grade_submission(
        conn, generator_id=row["generator_id"], instance_id=row["instance_id"],
        submission=answer, user_id=user_id, want_trace=False,
    )
    correct = bool(verdict["correct"])
    if existing and existing["correct"]:
        correct = True  # already solved today; keep the win
    conn.execute(
        "insert into daily_drop_attempt (user_id, day, track, correct, attempts, confidence, ts)"
        " values (?,?,?,?,?,?,?)"
        " on conflict(user_id, day, track) do update set attempts=excluded.attempts,"
        " correct=max(daily_drop_attempt.correct, excluded.correct),"
        " confidence=coalesce(excluded.confidence, daily_drop_attempt.confidence), ts=excluded.ts",
        (user_id, row["day"], track, int(correct), attempts, confidence, now_iso()),
    )
    conn.commit()
    return {"correct": correct, "attempts": attempts, "solved": bool(correct),
            "feedback": verdict["feedback"], "trust_label": "VERIFIED"}


def history(conn: sqlite3.Connection, user_id: str, track: str = "gate_cse", days: int = 14) -> dict[str, Any]:
    rows = conn.execute(
        "select day, correct, attempts from daily_drop_attempt where user_id=? and track=?"
        " order by day desc limit ?", (user_id, track, days),
    ).fetchall()
    out = []
    for r in rows:
        if not r["correct"]:
            mark = "🔴"
        elif r["attempts"] == 1:
            mark = "🟩"
        elif r["attempts"] <= 3:
            mark = "🟡"
        else:
            mark = "🟧"
        out.append({"day": r["day"], "mark": mark, "attempts": r["attempts"]})
    share = "Daily Drop — EdGen\n" + "\n".join(f"{r['mark']} {r['day'][5:]}" for r in reversed(out))
    return {"grid": out, "share_text": share, "track": track}
