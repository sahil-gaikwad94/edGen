# SystemsDesign

## 0. How to read this
Product-system design: what the system must do, the algorithms behind it, and the numbers it must hit. Component-level technical detail lives in architecture.md.

## 1. Requirements
### Functional
- Browse tracks and lenses; see the skill tree.
- Placement diagnostic; daily plan; lessons; practice; feedback; reviews.
- Verified grading: numerics, code, notebooks, web apps, eval harnesses.
- Social: Daily Drop, Boss Fight, leagues, duels, share cards, challenge links.
- Career: portfolio, Skill Passport, interview simulator (later waves).
- Privacy: export and delete my data; track switch with credit.

### Non-functional targets (validate in W0)
- Lesson first content ≤ 2 s (stream blocks); cached lesson ≤ 1 s; uncached p95 ≤ 25 s.
- Problem serve ≤ 300 ms (pre-generated pools).
- Browser lab feedback ≤ 1 s; server judge p95 ≤ 10 s (code), ≤ 60 s (web/ML grading).
- Availability 99.5% at MVP; 99.9% for Boss Fight windows.
- Correctness: 100% of numeric answers from verified code; error-report rate < 1%.
- Marginal AI cost ≤ $0.005–0.02 per DAU-day (measure, then decide).

## 2. Concept Graph and track lenses
### Node
`id, title, kind (concept|skill|project), prereqs[], misconceptions[], sources[], difficulty_prior, generators[], est_minutes{depth}, version, reviewer`.

### Lens
`lens_id, goal_type (exam|role|mastery), weights w_L(n), ordering hints, milestones[], mock_config`.
- GATE weights come from historical marks per topic.
- Role weights come from job-description analysis + expert review.

### Authoring pipeline
1. LLM drafts nodes and edges from official syllabi and role profiles.
2. Human review per subject.
3. Automated checks: acyclic, no orphans, coverage vs past papers / job corpora.
4. Publish immutable graph version; node merges use an alias table so Twin history survives.
5. Later: suggest new prerequisite edges from attempt data (if failures on B correlate with low mastery on A).

### Track switch
`lens_readiness(L) = Σ w_L(n) · m_eff(n) / Σ w_L(n)`. Show it before switching. Mastery on shared nodes carries over; nothing is reset.

## 3. Learner model (Twin)
### Mastery (per node): Bayesian Knowledge Tracing
- Parameters per skill: `p_init, p_learn, p_slip, p_guess`.
- After a correct answer: `P(L|c) = P(L)(1−slip) / [P(L)(1−slip) + (1−P(L))·guess]`.
- After an incorrect answer: `P(L|w) = P(L)·slip / [P(L)·slip + (1−P(L))(1−guess)]`.
- Then: `P(L') = P(L|obs) + (1 − P(L|obs))·p_learn`.
- Hinted-correct answers count as weaker evidence (inflate `guess` per hint level; calibrate on data).

### Forgetting (FSRS-style)
`R(Δt) = (1 + Δt / (9·S))^(−1)`, so R = 0.9 when Δt = S. Stability S grows with successful spaced reviews and is learned per node and learner, not a fixed constant.

### Effective mastery and frontier
- `m_eff = P(L) · R`.
- Frontier = nodes whose prerequisites have `m_eff ≥ 0.7` and own `m_eff ∈ [0.3, 0.7]`.

### Calibration
Learners give a confidence (e.g. 25/50/75/90%) before submitting. Track Brier score and a reliability curve per subject: "when you say 70%, you're right 52% of the time."

### Logging rules (from day one)
Every personalization decision stores `policy_id` and `propensity`. Without this, offline policy evaluation (inverse propensity weighting) is impossible later.

## 4. Planner
### By goal type
- **Exam:** maximize expected marks at the exam date. `Σ w_L(n) · E[m_eff at date | plan]` under the time budget, prerequisite order and decay.
- **Role:** maximize readiness gain per minute, with milestone constraints (quests, portfolio items) and a spaced-review floor.
- **Mastery:** maximize breadth of verified nodes with reviews due.

### Algorithm (greedy with lookahead)
1. Candidates = frontier ∪ due reviews (R < 0.85).
2. `gain(c)` = expected weighted improvement at the goal date if done vs skipped; `cost(c)` = estimated minutes.
3. Sort by gain/cost; enforce prerequisites; interleave topics (no more than 2 consecutive from one cluster); cap reviews at ~20% of time.
4. Reserve ~15% exploration (bandit) with logged propensities.
5. Output 3–5 items; re-plan after every session and nightly.

### Attempt Advisor (GATE, verify rules each cycle)
- For an MCQ with a 1/3 (1-mark) or 2/3 (2-mark) penalty, attempting has positive expected value when `p > 1/4`. Both penalties give the same threshold.
- MSQ and NAT have no negative marking, so always attempt. MSQ has no partial marking, so it needs every correct option.
- The coach shows your calibrated `p` per subject, then recommends attempt / skip, and reports it after mocks.

## 5. Content system
### Lesson IR (block graph)
Block types: `claim, intuition, example, counterexample, proof, viz, lab, check`. One IR renders to web, audio script, slides, chat-app text, reel.

### Cache-first personalization
- **Core:** shared, cached by `track × node × language × depth × style × core_version`.
- **Delta:** per-user patch (analogy, prerequisite refresher, your recurring mistake) from a small model.
- ~90% of tokens are shared. This is what makes "free" feasible.

### Pre-generation and QA
- ~1,800 nodes × 2 depths × 2 languages ≈ 7,200 cores. Generate offline in batches, then human-review the top ~300 most-visited nodes before launch. The long tail generates on demand.

### Trust badges on every item
- **VERIFIED:** executed proof, oracle, tests.
- **SOURCED:** source span from an open or licensed corpus.
- **MODEL:** generated, unverified. Factual MODEL claims are stripped or flagged.
- Judge-scored items (rubrics, postmortems) are labeled "judged".

### Freshness (matters most for the AI track)
Each node has a `review_by` date. Nodes tagged volatile (frameworks, model APIs) get automated source checks and a re-verification queue.

### Languages
English first; Hinglish and Hindi in W2. A glossary protects technical terms; bilingual reviewers spot-check; language is part of the cache key.

## 6. Verified-practice systems
### Problem Foundry (all numeric tracks)
- The LLM writes generator code, not questions.
- Trust = two independently written solvers agree on 10k+ seeds + property tests + hand-verified golden cases + one-time human review per generator.
- Distractors come from mistake models, tagged for diagnosis. Difficulty is calibrated with IRT once data exists.
- GATE catalog: scheduling, page replacement, cache mapping, DFA minimization, LL(1)/LR/SLR tables, subnetting/CIDR, FD closure and normal forms, B+ tree order/height, pipeline hazards, Dijkstra/MST, recurrences, K-maps, IEEE-754, TCP throughput, Banker's algorithm, disk scheduling.

### Code Arena
Hidden tests + generated property tests; failing inputs are shrunk to a minimal counterexample; sandboxed execution; client run for feedback, server re-run for ranked results.

### Match-the-Reference (ML)
Learner implements (linear/logistic regression, k-means, PCA, tree split, backprop for a small net, softmax-CE, Adam, attention). Grader compares outputs to a reference on hidden seeds within tolerance; **finite-difference gradient checks** verify backprop.

### Build Quests (Full Stack, AI, ML)
Spec + hidden test harness. Web: contract tests and Playwright in an isolated runner. Security scan and load-test thresholds are part of the score. The "Staff Reviewer" agent comments on the diff, labeled "judged".

### Debug Foundries
- **Fault Foundry:** multi-service app + injected fault (race, N+1, leak, partition) + logs/metrics/traces. Graded on root cause, fix (symptom disappears under a load test), postmortem rubric.
- **ML Debug Foundry:** training code with an injected bug (leakage, wrong loss sign, missing zero_grad, eval-mode error). Known bug, so grading is deterministic.
- **Eval Foundry (AI):** broken RAG/agent; learner builds an eval harness and fixes it. Model calls replay recorded responses ("cassettes") for reproducibility and zero token cost.
- **Prompt-Injection Dojo:** run N attack payloads; score attack success rate with canary tokens.

### Reasoning-Diff
Typed steps first (W1); handwriting in W2 with a "I read step 3 as …, correct?" confirmation. Alignment against the oracle trace finds the first divergence. The LLM only words the explanation.

## 7. Social and growth systems
- **Daily Drop:** same seed per track per day; answer hash checked server-side; share a spoiler-free result grid.
- **Boss Fight:** weekly seed, 15-min timer, server-authoritative; async in W1, live later.
- **Leagues:** weekly cohorts of ~30 by track and level; promotion/relegation.
- **Duels:** shared seed, Elo/Glicko-2, loser's mistake auto-explained.
- **Share cards:** server-rendered images (result, Brain Print, rank).
- **SEO pages:** reviewed lesson cores publish as public pages; `noindex` until reviewed to avoid thin-content penalties.
- **Community fixes:** users flag or propose edits; Verifier checks; accepted fixes bump `core_version`.
- **Integrity:** server-side answer keys, time bounds, pattern checks. Offline practice is unranked.
- **Wellbeing:** streak freezes, rest days, no public shaming, quiet hours, no late-night streak pressure.

## 8. Career layer
### Skill Passport integrity tiers
- T0 self-claimed.
- T1 practice-verified (server-graded attempts).
- T2 viva-verified (randomized voice questioning with liveness checks).
- T3 proctored (institute-run).
Each credential is a signed, revocable link showing evidence at its tier. Viva recordings are sensitive: consent, short retention, access controls.

### Others
Portfolio Builder turns quest repos into README + resume bullets. Interview Simulator is role-based (DSA, system design, ML design).

## 9. Capacity and cost model (assumptions, replace with measured)
- Year-1 target: 100k MAU, 25k DAU, 3× peak in exam season, ~1,800 nodes.
- Events: ~44/DAU-day → ~1.1M/day → ~13/s average, ~400/s season peak. One Postgres with batching is enough at MVP.
- Event/attempt storage: ~0.5 KB/event → ~0.55 GB/day → ~200 GB/year raw.
- Core generation: ~7,200 cores one-off (about $360 at an assumed $0.05 each).
- Day-to-day: 100k lesson opens → ~5% core misses early on (~5k generations/day) + 100k small-model deltas.
- Foundry pools: ~200 generators × 5 difficulty buckets × 2,000 instances ≈ 2M instances ≈ 2 GB.
- Server sandboxes: assume 2% of DAU × 15 min ≈ 7,500 min/day ≈ 125 microVM-hours/day.
- AI cost: at $0.005–0.02 per DAU-day, 25k DAU ≈ $125–500/day (~$4k–15k/month). **This is the number that decides whether "free" is sustainable.** Measure the delta cost first in W0.
- Funding levers: infra/AI credits, grants, early institute contracts, Pro tier.

## 10. Trust, legal, privacy
- **DPDP (India):** children's data needs verifiable parental consent and restricts tracking. Keep adult-first; get counsel before opening JEE/NEET. (Not legal advice.)
- **Content licenses:** PYQs and coaching material are copyrighted (use original variants, link to official papers). NPTEL/MIT OCW licenses are often non-commercial, which may conflict with B2B. Store the license on every source. Check model and TTS voice licenses too.
- **Naming:** don't use "GATE"/IIT branding in a way that implies affiliation; add a disclaimer.
- **Twin data:** minimize, never sell, one-click export/delete, opt-in for IDE/browser companion and anonymous peer features.
- **Safety:** retrieved text is untrusted input; sandbox isolation; abuse detection.

## 11. Metrics and experiments
- North star: weekly verified mastery gains per WAU.
- Activation: first verified problem within 10 minutes.
- Retention: D1/D7/D30 per track.
- Learning: pre/post diagnostic delta, mock score delta (GATE), quests passed (career tracks).
- Quality: error-report rate, verifier veto rate, cache hit rate, judge disagreement rate.
- Economics: AI cost per DAU-day, split by feature.
- Growth: invites per active user, K, SEO signups.
- Guardrails: late-night usage spikes, rapid-fail loops.
- Experiments: 5% global holdout without personalization to measure Twin lift; canary rollouts on fast proxies (next-day success, completion, thumbs, error reports).

## 12. Roadmap and gates
- **W0 (weeks 0–1):** concierge test; graph v0 (DBMS + OS, ~120 nodes); 5 generators. Gate: ≥ 60% finish a session; ≥ 30% return next day; delta cost measured.
- **W1 (days 1–90):** GATE CSE MVP, then full syllabus + mocks. Gate: D7 ≥ 15%, error rate < 2%, cost within 2× target.
- **W2 (days 60–120):** Full Stack + ML tracks, Code Arena, Match-the-Reference, leagues, duels, Hinglish, offline. Gate: ≥ 25% of new-track users complete a first quest.
- **W3 (days 120–200):** AI track, Debug/Eval/Fault Foundries, Skill Passport, interview simulator, institute dashboard. Gate: first paying institute pilot.

## 13. Risks and mitigations
- Scope creep → hard cut line; one in, one out.
- AI cost → cache, small models, metering of generative features only, per-run budgets.
- Wrong content → block-level verification, badges, report button, review of top nodes.
- Leaderboard cheating → server keys, time bounds, pattern checks.
- Stale AI content → `review_by` dates, source monitoring.
- Peak season load (GATE Jan–Feb) → pre-warm caches, autoscale workers on queue depth.
- Sandbox abuse → egress deny, quotas, CPU-anomaly kill.
- Vendor lock-in → model gateway with fallbacks.
- Reviewer bottleneck → paid and volunteer reviewers, review top nodes first.

## 14. Open decisions
Name; web-first vs mobile-first; reviewer plan; model hosting budget; whether the ML lens includes a GATE DA exam mode in W2.
