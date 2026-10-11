"""Security helpers: idempotency (architecture §19) and verdict signing (ADR 5)."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3

from . import config
from .db import dumps, loads, now_iso


def sign_verdict(verdict: dict) -> str:
    payload = json.dumps(verdict, sort_keys=True, separators=(",", ":"))
    return hmac.new(config.VERDICT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(verdict: dict, signature: str) -> bool:
    return hmac.compare_digest(sign_verdict(verdict), signature)


def idempotent_response(conn: sqlite3.Connection, user_id: str, key: str | None, endpoint: str) -> dict | None:
    if not key:
        return None
    row = conn.execute(
        "select response from idempotency where user_id=? and key=? and endpoint=?",
        (user_id, key, endpoint),
    ).fetchone()
    if row:
        return loads(row["response"])
    return None


def store_idempotent(conn: sqlite3.Connection, user_id: str, key: str | None, endpoint: str, response: dict) -> None:
    if not key:
        return
    conn.execute(
        "insert or replace into idempotency (user_id, key, endpoint, response, created_at) values (?,?,?,?,?)",
        (user_id, key, endpoint, dumps(response), now_iso()),
    )
    conn.commit()
