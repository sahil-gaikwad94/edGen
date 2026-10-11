"""Adaptive placement diagnostic (ideaBrief §7): 8 items, ~10 minutes.

policy_id=placement_v1; propensity logged per item (selection probability).
Diagnostic items deliberately span both subjects and difficulty buckets.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from edgen_foundry import get_generator

from ..content import get_content
from ..db import dumps, loads, now_iso
from . import twin_svc
from .judge_svc import serve_instance

POLICY_ID = "placement_v1"

# (generator, bucket) with mode hints — spans OS + DBMS as in W0 scope
_BLUEPRINT = [
    ("os.page_replacement", 2, "fifo"),
    ("dbms.serializability", 2, None),
    ("os.cpu_scheduling", 2, "rr"),
    ("dbms.fd_closure", 2, "keys"),
    ("os.disk_scheduling", 3, None),
    ("os.page_replacement", 3, "lru"),
    ("os.cpu_scheduling", 3, "srtf"),
    ("dbms.fd_closure", 3, "normal_form"),
]
PROPENSITY = 1.0 / len(_BLUEPRINT)


def start(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    items = []
    used: set[str] = set()
    for i, (gen_id, bucket, mode) in enumerate(_BLUEPRINT):
        served = serve_instance(conn, gen_id, bucket, user_id=user_id, exclude=used)
        used.add(served["instance_id"])
        # bias params by mode where the blueprint says so
        params = loads(conn.execute(
            "select params from instance_pool where instance_id=?",
            (served["instance_id"],),
        ).fetchone()["params"])
        if mode and params.get("mode") != mode:
            # find an instance of this generator+bucket with the right mode
            alt = conn.execute(
                "select i.instance_id, i.params from instance_pool i where i.generator_id=? and i.bucket=?"
                " and json_extract(i.params, '$.mode')=? order by random() limit 1",
                (gen_id, bucket, mode),
            ).fetchone()
            if alt:
                gen = get_generator(gen_id)
                p = loads(alt["params"])
                served = {
                    "instance_id": alt["instance_id"],
                    "generator_id": gen_id,
                    "bucket": bucket,
                    "node_id": gen.node_for(p),
                    "statement": gen.statement(p),
                    "input_spec": gen.input_spec,
                    "hints": gen.hints,
                }
                used.add(alt["instance_id"])
        items.append(served)
    state = {
        "items": items, "idx": 0, "status": "in_progress", "started_at": now_iso(),
    }
    conn.execute(
        "insert or replace into diagnostic_state (user_id, items, idx, status, started_at) values (?,?,?,?,?)",
        (user_id, dumps(items), 0, "in_progress", state["started_at"]),
    )
    conn.commit()
    return _public(items, 0, "in_progress")


def current(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from diagnostic_state where user_id=?", (user_id,)).fetchone()
    if row is None:
        return None
    return _public(loads(row["items"]), row["idx"], row["status"])


def answer(conn: sqlite3.Connection, user_id: str, idx: int, submission: Any,
           confidence: int | None, hint_level: int = 0) -> dict[str, Any]:
    from .judge_svc import grade_submission

    row = conn.execute("select * from diagnostic_state where user_id=?", (user_id,)).fetchone()
    if row is None:
        return {"error": "no_diagnostic"}
    items = loads(row["items"])
    if row["status"] == "complete":
        return {"error": "already_complete"}
    if idx != row["idx"]:
        return {"error": "out_of_order", "expected": row["idx"]}

    item = items[idx]
    verdict = grade_submission(
        conn, generator_id=item["generator_id"], instance_id=item["instance_id"],
        submission=submission, user_id=user_id, want_trace=False,
    )
    content = get_content()
    node_id = verdict["node_id"]
    node = content.graph.get(node_id)
    before, after = twin_svc.apply_attempt(
        conn, user_id=user_id, node_id=node_id, correct=bool(verdict["correct"]),
        confidence=confidence, hint_level=hint_level, error_tag=verdict.get("error_tag"),
        policy_id=POLICY_ID, propensity=PROPENSITY, p_init=node.difficulty_prior,
    )
    twin_svc.record_attempt(
        conn, attempt_id=str(uuid.uuid4()), user_id=user_id, node_id=node_id,
        instance_id=item["instance_id"], judge_job_id=verdict["judge_job_id"],
        generator_id=item["generator_id"], correct=bool(verdict["correct"]),
        confidence=confidence, hint_level=hint_level, latency_ms=None,
        error_tag=verdict.get("error_tag"), steps=None,
        policy_id=POLICY_ID, propensity=PROPENSITY,
    )
    next_idx = idx + 1
    status = "complete" if next_idx >= len(items) else "in_progress"
    conn.execute("update diagnostic_state set idx=?, status=? where user_id=?",
                 (next_idx, status, user_id))
    conn.commit()
    return {
        "correct": bool(verdict["correct"]),
        "feedback": verdict["feedback"],
        "error_tag": verdict.get("error_tag"),
        "mastery": {"node_id": node_id, "before": round(before.p_known, 3),
                    "after": round(after.p_known, 3)},
        "idx": next_idx,
        "total": len(items),
        "status": status,
        "propensity": PROPENSITY,
        "policy_id": POLICY_ID,
    }


def _public(items: list, idx: int, status: str) -> dict[str, Any]:
    safe = [
        {"idx": i, "generator_id": it["generator_id"], "statement": it["statement"],
         "input_spec": it["input_spec"], "instance_id": it["instance_id"],
         "hints": it.get("hints", [])}
        for i, it in enumerate(items)
    ]
    return {"items": safe, "idx": idx, "total": len(items), "status": status,
            "policy_id": POLICY_ID, "propensity": PROPENSITY}
