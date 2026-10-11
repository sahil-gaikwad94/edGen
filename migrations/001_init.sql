-- EdGen schema v1 (architecture.md §4, §5, §7, §18).
-- Phase 1 runs in-memory (edgen.store.state); this is the target schema that the
-- store interfaces plug into. Apply with: psql "$DATABASE_URL" -f migrations/001_init.sql

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- graph (§4) --
create table if not exists concept_node (
  id text, graph_version int, title text, kind text,
  prereqs text[], difficulty_prior real, volatile bool, review_by date,
  primary key (id, graph_version)
);

create table if not exists node_alias (old_id text primary key, new_id text);

create table if not exists lens (
  id text primary key, goal_type text, config jsonb  -- milestones, mock config
);

create table if not exists lens_node (
  lens_id text, node_id text, weight real, ord int,
  primary key (lens_id, node_id)
);

-- ------------------------------------------------------- agent runtime (§5) --
create table if not exists run_events (
  run_id uuid, seq int, ts timestamptz default now(),
  type text, agent text, payload jsonb, parent_seq int, hash text,
  primary key (run_id, seq)
) partition by hash (run_id);

-- --------------------------------------------------------- twin service (§7) --
create table if not exists twin_state (
  user_id uuid, node_id text, p_known real, stability_days real,
  last_seen timestamptz, attempts int,
  primary key (user_id, node_id)
);

create table if not exists attempt (
  id uuid primary key,            -- client-generated UUIDv7, idempotent
  user_id uuid, node_id text, instance_id uuid, judge_job_id uuid,
  correct bool, confidence smallint, hint_level smallint,
  latency_ms int, error_tag text,
  policy_id text, propensity real, ts timestamptz default now()
);
create index if not exists attempt_user_ts on attempt (user_id, ts desc);
create index if not exists attempt_user_node on attempt (user_id, node_id);

create table if not exists calibration_bin (
  user_id uuid, subject text, conf_bin smallint, n int, n_correct int,
  primary key (user_id, subject, conf_bin)
);

-- ---------------------------------------------------------- core data (§18) --
create table if not exists instance_pool (
  generator_id text, version int, bucket smallint, instance_id uuid,
  params jsonb, primary key (generator_id, version, instance_id)
);

create table if not exists judge_job (
  id uuid primary key, kind text, user_id uuid, spec_ref text,
  status text, verdict jsonb, signature text, created_at timestamptz
);

create table if not exists share_artifact (
  id uuid primary key, user_id uuid, kind text, payload jsonb, created_at timestamptz
);

-- Retention (architecture §18): run_events hot 90 days then archived; attempts
-- are kept because they are the source of truth for rebuilding the Twin.
