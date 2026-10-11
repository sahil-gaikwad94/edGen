# EdGen

**Verified-Practice Learning Agent.** A free, AI-native learning app where one
personal learner model (the *Twin*) teaches, tests, diagnoses and plans across
four tracks: GATE CSE, Full Stack, AI and ML.

> Every number is computed by code. Every claim carries a receipt.

This repository is the **Phase 1** build: the deterministic spine that the whole
product depends on. See `indeaBrief.md`, `SystemsDesign.md` and `architecture.md`
for the full product/system design.

## What's in Phase 1

| Area | Module | Doc anchor |
| --- | --- | --- |
| Trust tiers + receipts (VERIFIED / SOURCED / JUDGED / MODEL) | `edgen.trust` | architecture §11 ADR |
| Concept Graph + lens engine (versions, aliases, readiness, frontier) | `edgen.graph` | SystemsDesign §2, architecture §4 |
| Twin: BKT mastery, FSRS forgetting, calibration, propensities | `edgen.twin` | SystemsDesign §3, architecture §7 |
| Planner (Today) + Attempt Advisor | `edgen.planner` | SystemsDesign §4 |
| Foundry: dual-solver differential verification, instance pools | `edgen.foundry` | SystemsDesign §6, architecture §18 |
| Lesson IR + renderer + receipts | `edgen.lesson` | SystemsDesign §5, architecture §6 |
| FastAPI v1 API | `edgen.api` | architecture §19 |

## Quick start

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/pytest            # run the test suite
.venv/bin/edgen serve       # run the API on :8000
```

Then open `http://localhost:8000/docs` for the API, or:

```bash
curl localhost:8000/v1/tracks
curl "localhost:8000/v1/tree?lens=gate_cse"
curl "localhost:8000/v1/plan/today?lens=gate_cse"
```

## The trust model

Deterministic practice (Foundry, Code Arena, Match-the-Reference) has near-zero
marginal cost, so it stays unlimited and free. Its answers are never an LLM guess:
a generator ships only when **two independently written solvers agree** across
thousands of seeds plus property tests and hand-verified golden cases. See
`edgen.foundry.verify`.

## Layout

```
src/edgen/{trust,graph,twin,planner,foundry,lesson,api,store}
src/edgen/content/                          # versioned content artifacts
tests/                                      # maths proofs + trust properties
migrations/                                 # Postgres schema
```

The architecture doc proposes an `/apps` + `/packages` split. Phase 1 ships a
single importable package so it runs and tests cleanly; the module boundaries map
1:1 to those future services and can be extracted when scale demands it.
