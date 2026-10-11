"""Foundry instance pools + judge grading (architecture §9/§10).

Answer keys never leave the server: serving returns statement + input_spec only;
grading happens here against pool params. Verdicts are HMAC-signed.
"""
from __future__ import annotations

import random
import sqlite3
import uuid
from typing import Any

from edgen_foundry import get_generator, all_generators
from edgen_foundry.protocol import MistakeModel

from .. import config
from ..content import get_content
from ..db import dumps, loads, now_iso
from ..security import sign_verdict


class UnknownGenerator(Exception):
    pass


class NoInstance(Exception):
    pass


def published_ids() -> list[str]:
    return sorted(get_content().published_generators)


def ensure_pool(conn: sqlite3.Connection) -> dict[str, int]:
    """Warm pools for every published generator × bucket (idempotent)."""
    content = get_content()
    created: dict[str, int] = {}
    for gen_id, reg in content.published_generators.items():
        gen = get_generator(gen_id)
        version = int(reg.get("version", 1))
        per_bucket = int(reg.get("instances_per_bucket", config.POOL_INSTANCES_PER_BUCKET))
        for bucket in range(1, int(reg.get("buckets", config.POOL_BUCKETS)) + 1):
            n = conn.execute(
                "select count(*) c from instance_pool where generator_id=? and version=? and bucket=?",
                (gen_id, version, bucket),
            ).fetchone()["c"]
            for i in range(n, per_bucket):
                rng = random.Random(f"{gen_id}:v{version}:b{bucket}:{i}")
                params = gen.sample(rng, bucket)
                answer = gen.answer_key(params, gen.solve_a(params))
                node_id = gen.node_for(params)
                conn.execute(
                    "insert or ignore into instance_pool (generator_id, version, bucket, instance_id, params, answer, node_id, created_at)"
                    " values (?,?,?,?,?,?,?,?)",
                    (gen_id, version, bucket, str(uuid.uuid4()), dumps(params), answer, node_id, now_iso()),
                )
                created[gen_id] = created.get(gen_id, 0) + 1
    conn.commit()
    return created


def serve_instance(conn: sqlite3.Connection, generator_id: str, bucket: int = 2,
                   user_id: str | None = None, exclude: set[str] | None = None) -> dict[str, Any]:
    if generator_id not in published_ids():
        raise UnknownGenerator(generator_id)
    reg = get_content().published_generators[generator_id]
    rows = conn.execute(
        "select instance_id, params from instance_pool where generator_id=? and version=? and bucket=?",
        (generator_id, int(reg.get("version", 1)), bucket),
    ).fetchall()
    if not rows:
        raise NoInstance(generator_id)
    if user_id:
        attempted = {r["instance_id"] for r in conn.execute(
            "select distinct instance_id from attempt where user_id=? and instance_id is not null", (user_id,))}
        fresh = [r for r in rows if r["instance_id"] not in attempted and r["instance_id"] not in (exclude or set())]
        if fresh:
            rows = fresh
    row = random.SystemRandom().choice(rows)
    params = loads(row["params"])
    gen = get_generator(generator_id)
    return {
        "instance_id": row["instance_id"],
        "generator_id": generator_id,
        "bucket": bucket,
        "node_id": gen.node_for(params),
        "statement": gen.statement(params),
        "input_spec": gen.input_spec,
        "hints": gen.hints,
    }


def grade_submission(
    conn: sqlite3.Connection,
    *,
    generator_id: str,
    instance_id: str,
    submission: Any,
    user_id: str | None = None,
    want_trace: bool = True,
) -> dict[str, Any]:
    row = conn.execute("select * from instance_pool where instance_id=?", (instance_id,)).fetchone()
    if row is None or row["generator_id"] != generator_id:
        raise NoInstance(instance_id)
    gen = get_generator(generator_id)
    params = loads(row["params"])
    correct = gen.check(params, submission)

    error_tag = None
    feedback = None
    if not correct:
        for m in _matching_mistakes(gen, params, submission):
            error_tag = m.tag
            feedback = m.title + " — " + m.feedback
            break
        if feedback is None:
            feedback = "Not correct yet — open the oracle trace below and find where your path diverges."

    trace = [s.text for s in gen.trace(params)] if want_trace else []
    verdict = {
        "score": 1.0 if correct else 0.0,
        "checks": [{"name": "answer_key", "pass": correct, "detail": "server-side verified answer key"}],
        "artifacts": [],
        "trace": trace,
        "trust_label": "VERIFIED",
        "generator_id": generator_id,
        "instance_id": instance_id,
        "correct": correct,
        "error_tag": error_tag,
        "feedback": feedback,
        "node_id": gen.node_for(params),
        "graded_at": now_iso(),
    }
    verdict["signature"] = sign_verdict(verdict)
    job_id = str(uuid.uuid4())
    conn.execute(
        "insert into judge_job (id, kind, user_id, generator_id, instance_id, spec, submission, status, verdict, signature, created_at)"
        " values (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, "foundry", user_id, generator_id, instance_id, dumps({"bucket": row["bucket"]}),
         dumps({"answer": submission}), "READY", dumps(verdict), verdict["signature"], now_iso()),
    )
    conn.commit()
    verdict["judge_job_id"] = job_id
    return verdict


def _matching_mistakes(gen, params, submission) -> list[MistakeModel]:
    try:
        for m in gen.mistakes(params):
            if gen.canonical(m.answer) == gen.canonical(submission):
                return [m]
    except Exception:
        return []
    return []
