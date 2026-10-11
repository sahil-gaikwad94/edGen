import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Nav from "../components/Nav";
import { api, ensureSession } from "../lib/api";
import { mdToHtml } from "../lib/md";

const CONF = [25, 50, 75, 90];

export default function Diagnostic() {
  const router = useRouter();
  const [session, setSessionState] = useState(null);
  const [diag, setDiag] = useState(null);
  const [confidence, setConfidence] = useState(null);
  const [answer, setAnswer] = useState("");
  const [hint, setHint] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await ensureSession();
        if (!alive) return;
        setSessionState(s);
        const d = await api("/v1/diagnostic", { session: s });
        if (!alive) return;
        if (d.status === "complete") {
          router.replace("/today");
          return;
        }
        setDiag(d);
      } catch (e) {
        if (!alive) return;
        if (e.status === 404) router.replace("/");
        else setError(e.message);
      }
    })();
    return () => { alive = false; };
  }, [router]);

  const item = diag?.items?.[diag.idx];

  async function submit() {
    if (!item || confidence == null || busy || String(answer).trim() === "") return;
    setBusy(true);
    setError(null);
    try {
      const rawAnswer = String(answer).trim();
      const out = await api("/v1/diagnostic/answer", {
        method: "POST",
        session,
        body: {
          idx: item.idx,
          answer: item.input_spec?.kind === "number" ? Number(rawAnswer) : rawAnswer,
          confidence,
          hint_level: hint,
        },
      });
      setResult(out);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (result.status === "complete") {
      router.push("/today");
      return;
    }
    setResult(null);
    setAnswer("");
    setConfidence(null);
    setHint(0);
    setDiag((d) => ({ ...d, idx: result.idx }));
  }

  const progressIndex = diag ? Math.min(diag.idx + (result ? 1 : 0), diag.total) : 0;

  return (
    <>
      <Nav />
      <div className="narrow" style={{ paddingTop: 28 }}>
        <h1>Placement diagnostic</h1>
        <p className="muted small">
          Eight verified problems, ~10 minutes. Confidence first — the Twin calibrates on what you <em>think</em> you know.
        </p>

        {diag && (
          <div className="progress-dots" role="group" aria-label={`Question ${progressIndex} of ${diag.total}`}>
            <span className="sr-only">Question {progressIndex} of {diag.total}</span>
            {diag.items.map((_, i) => (
              <span key={i} aria-hidden="true" className={`dot ${i < progressIndex ? "done" : i === diag.idx ? "now" : ""}`} />
            ))}
          </div>
        )}

        {error && <div className="error-text" role="alert">{error}</div>}
        {!diag && !error && <p className="muted" role="status">Loading your diagnostic…</p>}

        {item && !result && (
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <span className="mono small muted">Q{diag.idx + 1} / {diag.total} · {item.generator_id}</span>
              <span className="badge badge-verified">VERIFIED GRADING</span>
            </div>
            <div className="statement mt" dangerouslySetInnerHTML={{ __html: mdToHtml(item.statement) }} />

            <div className="field" style={{ marginTop: 16 }}>
              <label>How confident are you? (this is recorded)</label>
              <div className="confidence-row" role="group" aria-label="Choose confidence">
                {CONF.map((c) => (
                  <button key={c} type="button" className={`conf-btn ${confidence === c ? "sel" : ""}`}
                    aria-pressed={confidence === c} onClick={() => setConfidence(c)}>
                    {c}%
                  </button>
                ))}
              </div>
            </div>

            <div className="field">
              <label htmlFor="diagnostic-answer">Your answer</label>
              <div className="answer-row">
                <input
                  id="diagnostic-answer"
                  className="answer-input"
                  type={item.input_spec?.kind === "number" ? "number" : "text"}
                  inputMode={item.input_spec?.kind === "number" ? "decimal" : "text"}
                  value={answer}
                  placeholder={item.input_spec?.placeholder || "answer"}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
                <button className="btn" onClick={submit}
                  disabled={busy || confidence == null || String(answer).trim() === ""}>
                  {busy ? "Grading…" : "Submit"}
                </button>
              </div>
              {item.input_spec?.hint && <div className="small muted">{item.input_spec.hint}</div>}
            </div>

            <button className="btn btn-ghost btn-sm" onClick={() => setHint((h) => Math.min(4, h + 1))}
              disabled={hint >= 4} aria-expanded={hint > 0} aria-controls={hint > 0 ? "diagnostic-hint" : undefined}>
              {hint === 0 ? "Need a hint? (never answer-first)" : `Hint ${hint} of 4 — show next`}
            </button>
            {hint > 0 && <div className="hint-box" id="diagnostic-hint" role="status" aria-live="polite">{item.hints?.[hint - 1]}</div>}
          </div>
        )}

        {result && (
          <div className="card">
            <div className={`verdict-banner ${result.correct ? "verdict-ok" : "verdict-no"}`} role="status" aria-live="polite">
              {result.correct ? "✓ Correct" : "✗ Not yet"}{"  "}
              <span className="badge badge-verified" style={{ marginLeft: 8 }}>VERIFIED</span>
            </div>
            {!result.correct && result.feedback && (
              <p className="small" style={{ marginTop: 10 }}>{result.feedback}</p>
            )}
            <div className="stat-row mt">
              <div className="stat">
                <div className="v">{result.mastery.before} → {result.mastery.after}</div>
                <div className="k">P(mastery) · {result.mastery.node_id}</div>
              </div>
              <div className="stat">
                <div className="v">{result.idx}/{result.total}</div>
                <div className="k">answered</div>
              </div>
            </div>
            <div className="mt">
              <button className="btn" onClick={next}>
                {result.status === "complete" ? "See your plan →" : "Next question →"}
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
