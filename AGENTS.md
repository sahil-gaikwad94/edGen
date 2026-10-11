# AGENTS.md — EdGen working notes

Persistent memory for agents working in this repo. Keep it short and current.

## What this is

EdGen is a free, AI-native learning app: one personal learner model (the *Twin*)
teaches, tests, diagnoses and plans across four tracks (GATE CSE, Full Stack, AI,
ML). Two non-negotiables:

1. **Every number is computed by code** — no LLM arithmetic on graded answers.
2. **Every claim carries a receipt** — trust badges (VERIFIED / SOURCED / JUDGED /
   MODEL) are part of the data model, not decoration.

Source-of-truth docs (read them before big changes):
`indeaBrief.md` (vision), `SystemsDesign.md` (algorithms + target numbers),
`architecture.md` (components, schema, ADRs).

## Commands

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e ".[dev]"

.venv/bin/pytest                                  # 91 tests
.venv/bin/ruff check src tests                    # must be clean
.venv/bin/edgen verify --seeds 5000               # Foundry dual-solver verification
.venv/bin/edgen plan --user demo                  # print today's plan
.venv/bin/edgen serve                             # API on :8000, docs at /docs
```

## Conventions

- Python 3.11+ (dev venv is 3.13). Line length 100. Ruff rules: E,F,I,UP,B,C4,SIM.
- All imports at the top of the file.
- Pydantic v2 models for anything crossing a boundary (API, IR, receipts).
- Determinism everywhere: RNG seeded from an explicit `seed`; instance ids derived
  from `generator@version:seed`. Never call `random` without a seed in compute paths.
- Node ids are dotted, namespaced under `cs.*` (e.g. `cs.os.scheduling`,
  `cs.dbms.normalization.fd_closure`). Track names live in `_GATE_WEIGHTS` as the
  top two parts (`cs.os`, `cs.dbms`).
- Content is data: graph nodes in `content/graph_v0.py`, lens weights in
  `content/lenses.py`, lesson cores in `content/lessons.py`. The engine in
  `graph/`, `planner/`, `lesson/` stays content-agnostic.

## Module map

| Module | Responsibility | Doc anchor |
| --- | --- | --- |
| `edgen.trust` | Trust tiers, receipts, weakest-tier badge composition | architecture ADR #11 |
| `edgen.graph` | Concept Graph + Lens: versions, aliases, readiness, frontier | §4 |
| `edgen.twin` | BKT mastery, FSRS forgetting, calibration, error genome | §7 |
| `edgen.planner` | Today planner + Attempt Advisor | §8 |
| `edgen.foundry` | Generators + dual-solver verification + instance pools | §5/§18 |
| `edgen.lesson` | Lesson IR, renderers, core cache, personalization delta | §6 |
| `edgen.api` | FastAPI v1 surface, SEO lesson pages | §19 |
| `edgen.store` | In-memory app state (the seam for Postgres/Redis) | §4/§7/§18 |
| `edgen.content` | Versioned content artifacts loaded into the engine | §25 |

## The trust model (do not weaken)

A generator ships only when **two independently written solvers agree** across
seeds, property tests pass, and hand-verified golden cases hold. See
`edgen.foundry.verify.GeneratorVerifier` and `tests/test_foundry.py`. If you add a
generator: implement `build`, `solvers` (two), `distractors`; add a golden case;
run `edgen verify --seeds 5000`.

The API must **never** return the correct flag with a problem
(`/v1/problems` returns option strings only). Grading happens server-side against
the verified key.

## Gotchas

- `from __future__ import annotations` + a local `TypeAlias` used as a FastAPI
  annotation breaks dependency resolution. Use `Depends(...)` directly as the
  default parameter value (B008 is ignored in `pyproject.toml` for this reason).
- The planner's documented frontier band `[0.3, 0.7)` excludes brand-new nodes
  (m_eff = 0). Candidates are therefore all unmastered nodes; `take()` pulls and
  schedules unmet prerequisites as a chain, and the frontier is reporting-only.
- `ConceptGraph` is built once per process and treated as immutable; graph changes
  ship as new `GraphVersion`s with `node_alias` entries for renames/merges.

## Status

Phase 1 (deterministic spine) is complete: graph+lens, Twin, planner+advisor,
Foundry (5 verified GATE generators, 5000-seed agreement), lesson IR+renderer,
FastAPI v1, Postgres migration, tests. Next phases: retrieval/verifier pipeline,
agent runtime + event log, the remaining tracks and graph coverage.
