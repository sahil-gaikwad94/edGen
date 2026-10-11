"""SQLite persistence — schema per architecture §4/§7/§18 (sqlite dialect).

Postgres 16 is the production target; the DDL below is written to port over
directly (json→jsonb, timestamptz→text, etc.). WAL mode + busy timeout for
the single-node MVP.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config

SCHEMA = """
create table if not exists app_user (
  id text primary key,
  created_at text not null,
  track text, lens text, goal_type text, goal_date text,
  minutes_per_day integer default 45,
  onboarded integer default 0,
  seed integer default 0
);

create table if not exists twin_state (
  user_id text not null, node_id text not null,
  p_known real not null, stability_days real not null default 30,
  last_seen_days real not null default 0,
  attempts integer not null default 0,
  error_tags text not null default '{}',
  primary key (user_id, node_id)
);

create table if not exists attempt (
  id text primary key,
  user_id text not null, node_id text, instance_id text, judge_job_id text,
  generator_id text, correct integer, confidence integer, hint_level integer,
  latency_ms integer, error_tag text, steps text,
  policy_id text, propensity real, ts text not null
);
create index if not exists idx_attempt_user on attempt(user_id, ts);

create table if not exists calibration_bin (
  user_id text not null, conf_bin integer not null,
  n integer not null default 0, n_correct integer not null default 0,
  primary key (user_id, conf_bin)
);

create table if not exists plan_event (
  id integer primary key autoincrement,
  user_id text not null, ts text not null, day text not null,
  seed integer, policy_id text, items text not null, log text
);

create table if not exists instance_pool (
  generator_id text not null, version integer not null, bucket integer not null,
  instance_id text primary key, params text not null, answer text not null,
  node_id text, created_at text not null
);
create index if not exists idx_pool_gb on instance_pool(generator_id, bucket);

create table if not exists judge_job (
  id text primary key, kind text not null, user_id text,
  generator_id text, instance_id text, spec text, submission text,
  status text not null, verdict text, signature text, created_at text not null
);

create table if not exists daily_drop (
  track text not null, day text not null,
  generator_id text not null, instance_id text not null,
  answer_hash text not null, primary key (track, day)
);

create table if not exists daily_drop_attempt (
  user_id text not null, day text not null, track text not null default 'gate_cse',
  correct integer not null default 0, attempts integer not null default 0,
  confidence integer, ts text not null,
  primary key (user_id, day, track)
);

create table if not exists model_call (
  id integer primary key autoincrement, ts text not null, feature text not null,
  tier text not null default 'T0', model text default 'none',
  tokens_in integer default 0, tokens_out integer default 0,
  cost_usd real default 0, cache_hit integer default 0, user_id text
);

create table if not exists idempotency (
  user_id text not null, key text not null, endpoint text not null,
  response text not null, created_at text not null,
  primary key (user_id, key, endpoint)
);

create table if not exists run (
  id text primary key, kind text not null, user_id text,
  status text not null, payload text, created_at text not null, updated_at text not null
);

create table if not exists run_events (
  run_id text not null, seq integer not null, ts text not null,
  type text not null, agent text, payload text,
  primary key (run_id, seq)
);

create table if not exists diagnostic_state (
  user_id text primary key, items text not null, idx integer not null default 0,
  status text not null, started_at text not null
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=WAL")
    conn.execute("pragma foreign_keys=ON")
    conn.execute("pragma busy_timeout=5000")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def loads(text, default=None):
    if text is None:
        return default
    return json.loads(text)
