import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Nav from "../../components/Nav";
import { api, ensureSession, newIdempotencyKey } from "../../lib/api";
import { mdToHtml } from "../../lib/md";

const CONF = [25, 50, 75, 90];

export default function Practice() {
  const router = useRouter();
  const { gen, node } = router.query;
  const [session, setSessionState] = useState(null);
  const [problem, setProblem] = useState(null);
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState(null);
  const [hint, setHint] = useState(0);
  const [steps, setSteps] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function loadProblem() {
    const s = await ensureSession();
    setSessionState(s);
    const p = await api(`/v1/problems/${gen}`, { session: s, query: { bucket: 2 } });
    setProblem(p);
    setResult(null);
    setAnswer("");
    setConfidence(null);
    setHint(0);
    setSteps("");
  }

  useEffect(() => {
    if (!gen) return;
    loadProblem().catch((e) => setError(e.message));
  }, [gen]);

  async function submit() {
    if (!problem || confidence == null || busy || String(answer).trim() === "") return;
    setBusy(true);
    setError(null);
    try {
      const out = await api("/v1/attempts", {
        method: "POST",
        session,
        idempotencyKey: newIdempotencyKey(),
        body: {
          generator_id: problem.generator_id,
          instance_id: problem.instance_id,
          answer: problem.input_spec?.kind === "number" && String(answer).trim() !== ""
            ? Number(answer)
            : answer,
          confidence,
          hint_level: hint,
          latency_ms: null,
          steps: steps.split("\n").map((x) => x.trim()).filter(Boolean),
          policy_id: "client_direct_v1",
          propensity: 1.0,
          lens: session?.lens || "gate_cse",
        },
      });
      setResult(out);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function nextProblem() {
    setProblem(null);
    loadProblem().catch((e) => setError(e.message));
  }

  const verdict = result?.verdict;
  const diff = result?.reasoning_diff;

  return (
    <>
      <Nav />
      <div className="narrow" style={{ paddingTop: 26 }}>
        <div className="small mono muted">
          <Link href="/today">today</Link> / {gen || "…"}
          {node ? <> · target: {node}</> : null}
        </div>

        {error && <div className="error-text" role="alert">{error}</div>}

        {problem && !result && (
          <div className="card" style={{ marginTop: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="mono small muted">bucket {problem.bucket} · {problem.node_id}</span>
              <span className="badge badge-verified">SERVER-SIDE KEY</span>
            </div>
            <div className="statement mt" dangerouslySetInnerHTML={{ __html: mdToHtml(problem.statement) }} />

            <div className="field" style={{ marginTop: 14 }}>
              <label>Confidence (calibrates your Twin)</label>
              <div className="confidence-row" role="group" aria-label="Choose confidence">
                {CONF.map((c) => (
                  <button key={c} type="button" className={`conf-btn ${confidence === c ? "sel" : ""}`}
                    aria-pressed={confidence === c} onClick={() => setConfidence(c)}>{c}%</button>
                ))}
              </div>
            </div>

            <div className="field">
              <label htmlFor="practice-answer">Answer</label>
              <div className="answer-row">
                <input
                  id="practice-answer"
                  className="answer-input"
                  type={problem.input_spec?.kind === "number" ? "number" : "text"}
                  inputMode={problem.input_spec?.kind === "number" ? "decimal" : "text"}
                  value={answer}
                  placeholder={problem.input_spec?.placeholder || "answer"}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
                <button className="btn" onClick={submit}
                  disabled={busy || confidence == null || String(answer).trim() === ""}>
                  {busy ? "Grading…" : "Submit for verdict"}
                </button>
              </div>
              {problem.input_spec?.hint && <div className="small muted">{problem.input_spec.hint}</div>}
            </div>

            <div className="field">
              <label htmlFor="practice-steps">Your steps (optional — enables Reasoning-Diff, one step per line)</label>
              <textarea id="practice-steps" className="steps-area" value={steps} onChange={(e) => setSteps(e.target.value)}
                placeholder={"draw the gantt chart\ncompute waiting per process\naverage"} />
            </div>

            <button className="btn btn-ghost btn-sm" onClick={() => setHint((h) => Math.min(4, h + 1))}
              disabled={hint >= 4} aria-expanded={hint > 0} aria-controls={hint > 0 ? "practice-hint" : undefined}>
              {hint === 0 ? "Hint ladder (never answer-first)" : `Hint ${hint} / 4`}
            </button>
            {hint > 0 && <div className="hint-box" id="practice-hint" role="status" aria-live="polite">{problem.hints?.[hint - 1]}</div>}
          </div>
        )}

        {result && verdict && (
          <div className="card" style={{ marginTop: 8 }}>
            <div className={`verdict-banner ${verdict.correct ? "verdict-ok" : "verdict-no"}`} style={{ marginTop: 0 }} role="status" aria-live="polite">
              {verdict.correct ? "✓ Correct" : "✗ Incorrect"} · score {verdict.score}{" "}
              <span className="badge badge-verified" style={{ marginLeft: 6 }}>{verdict.trust_label}</span>
              <span className="mono small" style={{ marginLeft: 10, opacity: 0.7 }}>
                sig {verdict.signature.slice(0, 12)}…
              </span>
            </div>

            {!verdict.correct && verdict.feedback && (
              <p style={{ marginTop: 12 }}><strong>{verdict.error_tag ? `Detected: ${verdict.error_tag}` : "Feedback"}</strong> — {verdict.feedback}</p>
            )}

            <div className="stat-row mt">
              <div className="stat">
                <div className="v">{result.mastery.p_known_before} → {result.mastery.p_known_after}</div>
                <div className="k">P(mastery) · {result.mastery.node_id}</div>
              </div>
              <div className="stat">
                <div className="v">{confidence}%</div>
                <div className="k">your confidence</div>
              </div>
            </div>

            {diff && !diff.aligned && diff.first_divergence && (
              <div className="divergence">
                <strong>Reasoning-Diff: divergence at your step {diff.first_divergence.learner_step}</strong>
                <div className="vs">
                  <div>
                    <div className="small muted">you wrote</div>
                    <div>{diff.first_divergence.your_text}</div>
                  </div>
                  <div>
                    <div className="small muted">oracle step {diff.first_divergence.oracle_at}</div>
                    <div>{diff.first_divergence.oracle_text}</div>
                  </div>
                </div>
              </div>
            )}
            {diff && diff.aligned && (
              <p className="small" style={{ color: "var(--verified)", marginTop: 10 }}>
                ✓ Your steps align with the oracle trace.
              </p>
            )}

            <details className="trace" open={!verdict.correct}>
              <summary>Oracle trace ({verdict.trace.length} steps — facts from code, not vibes)</summary>
              <ol>
                {verdict.trace.map((t, i) => <li key={i}>{t}</li>)}
              </ol>
            </details>

            <div className="mt" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="btn" onClick={nextProblem}>Next problem →</button>
              <Link href="/today" className="btn btn-ghost">Back to Today</Link>
            </div>
            <div className="small muted" style={{ marginTop: 10 }}>
              Plan re-optimised after this attempt · {result.plan?.items?.length} items waiting.
            </div>
          </div>
        )}

        {!problem && !error && <p className="muted">Preparing a verified instance from the pool…</p>}
      </div>
    </>
  );
}
