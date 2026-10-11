# IdeaBrief — Verified-Practice Learning Agent (working title: TBD)

## 1. One-liner
A free, AI-native learning app where one personal learner model (the Twin) teaches, tests, diagnoses and plans across four tracks: GATE CSE, Full Stack, AI, ML. Every number is computed by code, every claim carries a receipt.

## 2. The problem
- Docs and tutorials (MDN, W3Schools, GFG) are static and identical for everyone.
- ChatGPT explains well but forgets your mistakes and can't prove its answers.
- Video courses are passive. LeetCode-style sites practice without teaching.
- Coaching platforms are paid, batch-paced and one-size-fits-all.
- Nobody tells you *where* your reasoning broke, or what to study next given your deadline.

## 3. The solution
1. **Teach:** personalized lessons built from a shared cached core plus a thin personal layer.
2. **Test:** infinite practice whose answers come from verified code, not LLM guesses.
3. **Diagnose:** step-level feedback ("your 4th eviction diverged") and calibration feedback.
4. **Plan:** a daily plan that optimizes for your goal (exam marks or role readiness).

## 4. Who it's for
- **GATE CSE aspirant** (exam-driven, high intent). Beachhead.
- **Aspiring full-stack developer** (role-driven, wants a portfolio).
- **Aspiring AI engineer** (LLMs, agents, RAG, evals).
- **Aspiring ML engineer / researcher** (math, modeling, from-scratch skill).
- Later: JEE/NEET (minors, consent rules, weaker oracle fit), institutes and colleges (B2B).

## 5. How tracks work
- One global **Concept Graph** (~1.5–2k nodes at launch): `math.linear_algebra.eigen`, `cs.os.scheduling`, `web.http.caching`, `ml.optim.adam`, `ai.rag.chunking`.
- A **track is a lens**: a chosen subgraph + weights + goal type + milestones.
- Goal types: **exam** (date, marks weightage), **role** (readiness + portfolio), **mastery** (no deadline).
- Switching tracks keeps mastery on shared nodes. Example: "ML lens: 41% ready already, thanks to your GATE math and Python work."

## 6. The four tracks
### GATE CSE (exam goal)
- Scope: Engineering Math, Discrete Math, Digital Logic, COA, Programming & DS, Algorithms, TOC, Compiler Design, OS, DBMS, CN, General Aptitude.
- Format (GATE 2027 CSE): 3-hour CBT, 100 marks: GA 15, Engineering Math 13, core subject 72. MCQ has negative marking (1/3 and 2/3); MSQ/NAT have none; no partial marking in MSQ. Re-verify each cycle on the official site.
- Signature: Problem Foundry, Reasoning-Diff, Attempt Advisor, 3-hour mock simulator with Mistake Autopsy, PYQ Time Machine, Boss Fight.
- What is verified: scheduling, page replacement, cache, DFA minimization, LL/LR tables, subnetting, normal forms, B+ trees, pipeline hazards.

### Full Stack (role goal: SDE-1 full stack)
- Scope: web fundamentals, JS/TS, React, Next.js, Node + FastAPI, SQL/Postgres, NoSQL, auth and security, APIs, testing, Docker/CI-CD, cloud, performance, observability, system design, interviews.
- Signature: Build Quests (hidden tests + Playwright), Staff Reviewer (code review agent), Fault Foundry (debug a broken multi-service app), Rosetta delta-teaching, System Design Studio, Portfolio Builder.
- What is verified: API contract tests, SQL result-set equivalence, component tests, e2e tests, security scans, load-test thresholds.

### AI (role goal: AI engineer, applied)
- Scope: LLM fundamentals, structured outputs, tool use and agents, RAG, evals, LoRA fine-tuning, serving and cost, guardrails and prompt injection, multimodal, MCP/agent protocols, observability.
- Signature: Eval Foundry (broken RAG/agent to diagnose), Prompt-Injection Dojo, Agent Trace Debugger, Paper→Playground, labs that replay recorded model responses (free and reproducible).
- What is verified: retrieval recall on hidden question sets, citation-span faithfulness checks, attack success rate with canary tokens, budget/latency compliance. LLM-judged items are labeled "judged", never "verified".

### ML (role goal: ML engineer, or research; optional exam lens)
- Scope: math for ML, Python/NumPy/pandas, classical ML, evaluation and features, deep learning, optimization and training dynamics, CV/NLP, MLOps, interpretability, research reading.
- Signature: Match-the-Reference labs (implement from scratch, compared numerically to a reference), ML Debug Foundry (find the injected bug), gradient-check oracle, Training Dynamics Playground, Replication Radar.
- Optional lens: GATE DA-style exam prep on the same graph (verify its syllabus first).

## 7. Core loop
Pick track + goal date → 10-min placement diagnostic → skill tree → **Today** (3 items, ~45 min) → 5-min lesson → verified practice → feedback on where reasoning diverged → Twin updates → plan re-optimizes → share card / Boss Fight / Daily Drop.

## 8. Feature catalog (W1 = MVP, W2, W3, Later, Cut)
### Learn
- Concept Graph + Track Lenses [W1]
- Adaptive placement diagnostic [W1]
- Cache-first personalized lessons with receipts [W1]
- Hint Ladder: 4 levels, never answer-first [W1]
- Template visualizers (cache, B+ tree, scheduler Gantt) [W1]; generated animations [W3]
- Misconception cards ("why people get this wrong") [W2]
- Ghost Tutor personas (Feynman / visual / interview-grind) [W2]
- Hinglish and Hindi modes [W2]
- Rosetta delta-teaching (React↔Vue, Python↔Go, SQL↔NoSQL, PyTorch↔JAX) [W2]
- Explain-it-back (Feynman check, graded against a rubric) [W2]
- Equation→Executable (LaTeX → shape-checked code) [W2]
- Audio explainers / commute mode [W2]

### Practice
- Problem Foundry (verified infinite numericals) [W1]
- Daily Drop: one shared puzzle per track, spoiler-free share grid [W1]
- Code Arena: hidden tests, minimal counterexample shrinking [W2]
- Match-the-Reference labs [W2]
- Build Quests with auto-grading [W2 basic, W3 rich]
- Fault Foundry (backend chaos) [W3]
- ML Debug Foundry (injected training bugs) [W3]
- Eval Foundry + Prompt-Injection Dojo [W3]
- System Design Studio [W3]
- Paper→Playground + Replication Radar [W3]

### Diagnose
- Reasoning-Diff: typed steps [W1], handwriting [W2]
- Attempt Advisor + Calibration Coach (confidence → "attempt only if p > 0.25" for MCQ) [W2]
- Mistake Autopsy after mocks [W2]
- Error Genome (your mistake types across tracks) [W2]
- Struggle Detector (opt-in IDE/browser) [W3]

### Plan
- Today plan [W1]; Revive (daily 5-min spaced review with fresh variants) [W1]
- Track switch with credit transfer [W1]
- Exam-date optimizer [W2]; role-readiness plan and role roadmaps [W2]
- Weekly report [W2]

### Social and growth
- Share cards, challenge links, async weekly Boss Fight [W1]
- Public SEO lesson pages (cached cores) [W1]
- Leagues, 1v1 duels, study rooms (counts, not cursors) [W2]
- Community fixes that improve cached lessons [W2]
- Telegram revise bot [W2]; Auto-Reel [W3]; WhatsApp bot [Later]

### Career
- Portfolio Builder (repos + README from quests) [W3]
- Skill Passport: verifiable link with integrity tiers [W3]
- Voice Interview Simulator (role-based) [W3]
- Institute dashboards [W3]

### Platform
- Accessibility baseline, Twin export/delete [W1]
- Offline / Lite mode [W2]
- Public Twin API [Later]

## 9. What we will not do
- NFTs (use signed verifiable links).
- Friend-visible "Streak Jail" shaming (private nudges only).
- "Zero hallucination" claims (we show VERIFIED / SOURCED / MODEL badges instead).
- Per-learner always-on microVMs.
- Clone Battles at launch (revisit later).
- Live cursor presence (privacy and moderation cost).

## 10. Growth plan
- **SEO flywheel:** every cached, reviewed lesson core becomes a public page with an interactive lab.
- **Daily Drop** (Wordle-style grid) per track.
- **Brain Print and Boss rank cards** as by-products of learning.
- **Challenge links:** a friend lands on the same problem set.
- **Communities:** Telegram/Discord GATE groups, campus ambassadors, LinkedIn shares of Skill Passports.
- Target K ≈ 0.3. Virality multiplies retention. It doesn't replace it.

## 11. Business model
- Learners: free forever. Deterministic practice (Foundry, Code Arena, Match-the-Reference) has near-zero marginal cost, so it stays unlimited. Only LLM-heavy features are metered.
- Revenue: (1) institutes and colleges, (2) Pro power users (private Fault/Debug/Eval Foundries, interview simulator, Twin export), (3) Skill Passport verification for hiring.
- No ads for minors.

## 12. Success metrics
- North star: weekly verified mastery gains per WAU.
- Activation: first verified problem solved within 10 minutes.
- Retention hypotheses: D1 ≥ 35%, D7 ≥ 18%, D30 ≥ 8%.
- Per track: GATE = mock score delta; career tracks = quests passed and portfolio items shipped.
- Quality: error-report rate < 1%, verifier veto rate, cache hit rate.
- Economics: AI cost per DAU-day.

## 13. Launch sequence
- **W0 (weeks 0–1):** concierge test with ~20 aspirants on DBMS + OS.
- **W1 (days 1–90):** GATE CSE MVP, then full syllabus + mocks.
- **W2 (days 60–120):** Full Stack and ML tracks.
- **W3 (days 120–200):** AI track, heavy Foundries, career layer.

## 14. Name ideas (check trademark, domain, app stores)
Praxis, Anvil, Sutra, Drona, Guru Loop. Avoid "Hermes". Don't imply affiliation with GATE or the IITs.

## 15. Top risks
1. Scope creep: every new feature must replace one.
2. AI cost at scale: cache, small models, client-side compute, metering.
3. Wrong content: block-level verification, badges, report button, human review of top nodes.
4. Content licensing: original variants, store license per source.
5. Minors and consent: adult-first, JEE/NEET only after a consent flow.

## 16. Open questions
Final name; team size and weekly hours; model hosting budget; web-first PWA vs mobile-first; who reviews domain content (volunteers, paid reviewers).
