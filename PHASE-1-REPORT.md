# Phase 1 — build and verification report

**Status:** W0 trust gate complete; W1 core-loop skeleton working end-to-end. This phase delivers a local, testable product slice rather than the complete W1/90-day roadmap.

> **Follow-on update (2026-10-12):** The repository now also publishes complete, browsable syllabus maps for GATE CSE, Full Stack, Applied AI, and ML. GATE CSE remains the only track with an interactive slice (OS + DBMS); the other three are curriculum-only previews. Their module-hour totals are reconciled and validated at load time. This report's sections below document the original Phase-1 baseline and its then-current scope.

## Acceptance coverage

| Roadmap step | Delivered | Evidence |
|---|---|---|
| Onboarding: track + goal | GATE CSE track, exam-goal date, and daily-minute budget persist on the anonymous development session. Upcoming tracks are clearly marked. | Landing-page flow; `POST/PATCH /v1/session` |
| Eight-question placement | Fixed eight-item OS/DBMS diagnostic, confidence capture, verified grading, safe hints, and completion plan. | `POST /v1/diagnostic/start`, `/v1/diagnostic/answer`; smoke |
| Skill tree | 105-node OS/DBMS graph, prerequisites, learner-state labels, frontier/remediation, weighted readiness. | `/v1/tree`; graph tests |
| Today plan | Deterministic 3–5 item plan, gain/cost ranking, exploration, interleave/review controls, and logged policy propensities. | `/v1/plan/today`; planner tests |
| Lesson + trust badges | Nine receipt-validated authored lesson cores; remaining graph nodes receive a labeled draft scaffold. Includes Gantt, frames, FD graph, disk-track, and state-cycle templates. | `content/lessons/`; receipt tests; lesson UI |
| Verified practice | Server-held answers, HMAC-signed verdicts, confidence, four-level hint ladder, mistake-model feedback, oracle trace, and typed-step Reasoning-Diff. | `/v1/problems/{generator}`, `/v1/attempts`; API tests |
| Twin + re-plan | BKT-style knowledge update and retention/effective-mastery model persist after attempts; a new plan is generated after practice. | attempt response + persisted Twin; smoke |
| Daily Drop | Day-seeded shared puzzle, server grading, attempts/history, and spoiler-free emoji share grid. | `/v1/daily-drop`; API tests |
| Cost + privacy basics | Zero-cost model-call/cache metering; per-user export and delete endpoints. | `/v1/metrics/cost`, `/v1/me/data`; API tests |

## W0 trust gate

Graph v0 contains **105 concepts**: 55 OS and 50 DBMS. The five published generators each run two independent solvers, property checks, and their golden suite:

| Generator | Differential seeds | Property seeds | Golden cases | Result |
|---|---:|---:|---:|---|
| `dbms.fd_closure` | 10,000 | 1,500 | 8 | PASS |
| `dbms.serializability` | 10,000 | 1,500 | 3 | PASS |
| `os.cpu_scheduling` | 10,000 | 1,500 | 3 | PASS |
| `os.disk_scheduling` | 10,000 | 1,500 | 5 | PASS |
| `os.page_replacement` | 10,000 | 1,500 | 7 | PASS |

**Total:** zero solver disagreements, zero property failures, and zero failures across 26 golden cases. `content/foundry/registry.yaml` records the published status and pool policy (5 buckets × 60 instances per generator). Re-run with:

```bash
python scripts/verify_foundry.py --seeds 10000 --properties 1500
```

## Verification run

- `.venv/bin/python -m pytest -q` — **45 passed**.
- `make smoke` — **PASS** through onboarding, all eight diagnostic items, tree/plan, authored lesson, wrong and correct practice attempts, Twin/re-plan, Daily Drop, export, and delete. The smoke test uses a temporary database.
- `npm run build` in `apps/web` — **PASS**, all requested pages statically generated.
- HTTP smoke through the running Next `/api` rewrite — **PASS** for health/tracks, full diagnostic, lesson, practice, plan, and Daily Drop.
- Page HTTP checks — **200** for `/`, `/diagnostic`, `/tree`, `/today`, `/drop`, `/learn/os.scheduling.rr`, `/practice/os.cpu_scheduling`, and `/manifest.json`.

The test client currently emits a Starlette deprecation warning about its HTTP client adapter; it does not affect the passing tests.

## Important scope and known gaps

- The active curriculum is **GATE CSE with the OS + DBMS graph slice**. The graph is 105 nodes, within the brief's approximate W0 target; it is not the full GATE syllabus.
- Nine lessons are authored/reviewed. Other lessons use honest draft scaffolds; no live model credentials or hosted generation are required or used.
- Anonymous `X-User-Id` session scoping is a development mechanism, not authentication. Set a non-default verdict secret and add real auth before deployment.
- Full Stack, AI, and ML are roadmap placeholders, not usable tracks. Full mocks, role paths, accounts, production PostgreSQL, social identity, billing, and operational hardening remain out of scope.
- The W0 retention/return-rate gates require a user pilot and cannot be inferred from code tests. This report makes no claim about D1/D7 retention, learning efficacy, or production SLOs.

## Main implementation areas

- `packages/graph`, `twin`, `lesson-ir`, `foundry`, `planner` — domain models and algorithms.
- `apps/api/app` — FastAPI routes, SQLite persistence, services, metering, and signed grading.
- `apps/web` — Next.js pages-router UI and server-side API rewrite.
- `content/` — graph, tracks/lenses, published Foundry registry/goldens, source corpus, and authored lessons.
- `tests/`, `scripts/verify_foundry.py`, `scripts/smoke.py` — regression, trust, and end-to-end checks.
