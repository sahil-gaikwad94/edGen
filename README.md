# EdGen

**Verified-practice learning:** one learner model teaches, diagnoses, plans, and adapts. Every number is computed by code; claims carry a provenance badge.

This repository contains the W0 trust gate and a W1 end-to-end learning slice, plus complete, browsable curriculum maps for GATE CSE, Full Stack, Applied AI, and Machine Learning. The interactive GATE experience is currently focused on OS + DBMS; the other three tracks are syllabus previews, not active adaptive-learning paths. This is not a production launch.

## What works today

- **Graph v0:** 105 OS and DBMS concepts with prerequisite validation, track lenses, frontier/remediation, mastery, retention, and readiness.
- **Problem Foundry:** CPU scheduling, page replacement, disk scheduling, FD closure/normal forms, and conflict serializability. Published pools have five difficulty buckets and 60 seeded instances per bucket.
- **Trust gate:** two independently implemented solvers, property checks, golden cases, server-side answer keys, signed verdicts, mistake feedback, and oracle traces.
- **Learning loop:** onboarding and goal setup → eight-item placement diagnostic → skill tree → adaptive Today plan → lesson → confidence-rated practice and four-step hint ladder → typed reasoning diff → Twin update and re-plan → Daily Drop share grid.
- **Lessons:** nine authored cores with source-span / execution receipts and trust badges; uncovered nodes degrade to an explicitly marked draft scaffold.
- **Learner data:** cost/cassette metering, export, and delete routes.
- **Curricula:** complete authored syllabus maps for GATE CSE, Full Stack Engineering, Applied AI Engineering, and Machine Learning Engineering. Each map includes phases, module hours, topics, and practice outcomes; the declared totals are validated against module-hour sums at API startup.
- **Web:** responsive Next.js pages-router app with a midnight glass / editorial-violet design system, keyboard-visible focus, labeled controls, and live verdict/error feedback. The searchable syllabus catalogue and track detail pages make all four curricula discoverable while distinguishing the live GATE CSE OS + DBMS slice from syllabus-only tracks. All browser API traffic uses relative `/api/...` URLs; Next rewrites them to FastAPI.

GATE CSE has a partial interactive learning loop. Full Stack, Applied AI, and Machine Learning have complete curriculum maps, but their adaptive graphs, lessons, and verified graders are still staged.

## Requirements

- Python 3.11+
- Node.js 18.18+
- npm

## Run locally

From the repository root:

```bash
make install
make seed
```

Then run the API and web app in separate terminals:

```bash
make api
```

```bash
make web
```

Open <http://localhost:3000>. The API listens at <http://localhost:8000>; the web dev server proxies `/api/*` to it. Override that server-side destination with `EDGEN_API_ORIGIN` if needed. Browser code must continue to use relative API URLs.

The API uses an anonymous development session (`POST /v1/session`, then `X-User-Id`). This is not account authentication. The default verdict-signing secret is for local development only; set `EDGEN_VERDICT_SECRET` to a strong secret outside local development.

### Useful commands

```bash
make test
make smoke
python scripts/verify_foundry.py --seeds 10000 --properties 1500
cd apps/web && npm run build
```

- `make test` runs the unit and API suites against an isolated temporary database.
- `make smoke` exercises the whole API loop in a separate temporary database; it does not touch `data/`.
- `verify_foundry.py` runs the differential/property/golden publication gate. A generator that fails is not ready to publish.
- `make seed` creates the local database and prewarms the published instance pools. API startup also ensures pools exist.

## API and content notes

- API prefix: `/v1` (for example `/v1/tree`, `/v1/plan/today`, `/v1/lessons/{node_id}`, `/v1/problems/{generator_id}`, `/v1/attempts`, `/v1/diagnostic`, `/v1/daily-drop`).
- Published curriculum summaries are available at `/v1/syllabi`; `/v1/syllabi/{track_id}` returns the complete phased map. The API rejects missing tracks, malformed module/topic data, duplicate IDs, and hour totals that do not reconcile.
- Lessons are loaded from `content/lessons/`; source receipts are validated against the source corpus when content loads.
- Generator publication records and golden cases live in `content/foundry/`.
- The default local SQLite file is `data/edgen.db`. `EDGEN_DB`, `EDGEN_DATA`, `EDGEN_ROOT`, and `EDGEN_CONTENT` can override local paths.
- Model calls are disabled unless replayed from a cassette. Current W1 paths use authored content or graph-derived scaffolds; metering still records cache/miss behavior at zero cost.

## Current boundaries

Authentication/OAuth, hosted model integrations, interactive coverage beyond the GATE OS + DBMS slice, adaptive Full Stack/AI/ML paths, production PostgreSQL, payments, and social accounts are still staged. Published syllabi are curriculum maps, not a claim that each track has working lessons or graders. The exposed data model and interfaces are an MVP foundation, not a claim that these systems are launch-ready. EdGen is independent and is not affiliated with GATE, the IITs, or any exam authority. See [PHASE-1-REPORT.md](PHASE-1-REPORT.md) for the original Phase-1 build and verification record.
