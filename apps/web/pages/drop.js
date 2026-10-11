import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api, ensureSession } from "../lib/api";
import { mdToHtml } from "../lib/md";

const CONF = [25, 50, 75, 90];

export default function Drop() {
  const [session, setSessionState] = useState(null);
  const [drop, setDrop] = useState(null);
  const [history, setHistory] = useState(null);
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  async function load(s) {
    const [d, h] = await Promise.all([
      api("/v1/daily-drop", { session: s }),
      api("/v1/daily-drop/history", { session: s }),
    ]);
    setDrop(d);
    setHistory(h);
    if (d.your_attempt?.correct) setResult({ alreadySolved: true, attempts: d.your_attempt.attempts });
  }

  useEffect(() => {
    (async () => {
      const s = await ensureSession();
      setSessionState(s);
      load(s).catch((e) => setError(e.message));
    })();
  }, []);

  async function submit() {
    if (busy || confidence == null || String(answer).trim() === "") return;
    setBusy(true);
    setError(null);
    try {
      const out = await api("/v1/daily-drop/answer", {
        method: "POST", session,
        body: { answer: drop.input_spec?.kind === "number" ? Number(answer) : answer, confidence },
      });
      setResult(out);
      const h = await api("/v1/daily-drop/history", { session });
      setHistory(h);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function share() {
    const text = history?.share_text || "Daily Drop — EdGen";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      window.prompt("Copy your share grid:", text);
    }
  }

  return (
    <>
      <Nav />
      <div className="narrow" style={{ paddingTop: 26 }}>
        <h1>Daily Drop</h1>
        <p className="muted small">
          {drop?.streak_note || "One shared puzzle per track, every day."}
        </p>
        {error && <div className="error-text" role="alert">{error}</div>}

        {drop && (
          <div className="card" style={{ marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="mono small muted">{drop.day} · {drop.generator_id}</span>
              <span className="badge badge-verified">SHARED SEED</span>
            </div>
            <div className="statement mt" dangerouslySetInnerHTML={{ __html: mdToHtml(drop.statement) }} />

            {!result && (
              <>
                <div className="field" style={{ marginTop: 14 }}>
                  <label>Confidence</label>
                  <div className="confidence-row" role="group" aria-label="Choose confidence">
                    {CONF.map((c) => (
                      <button key={c} type="button" className={`conf-btn ${confidence === c ? "sel" : ""}`}
                        aria-pressed={confidence === c} onClick={() => setConfidence(c)}>{c}%</button>
                    ))}
                  </div>
                </div>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label htmlFor="drop-answer">Your answer</label>
                  <div className="answer-row">
                    <input id="drop-answer" className="answer-input"
                    type={drop.input_spec?.kind === "number" ? "number" : "text"}
                    inputMode={drop.input_spec?.kind === "number" ? "decimal" : "text"}
                    value={answer}
                    placeholder={drop.input_spec?.placeholder || "answer"}
                    onChange={(e) => setAnswer(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submit()} />
                    <button className="btn" onClick={submit}
                      disabled={busy || confidence == null || String(answer).trim() === ""}>
                      {busy ? "Checking…" : "Submit"}
                    </button>
                  </div>
                </div>
              </>
            )}

            {result && (
              <div className={`verdict-banner ${result.correct || result.alreadySolved ? "verdict-ok" : "verdict-no"}`} role="status" aria-live="polite">
                {result.correct || result.alreadySolved
                  ? `✓ Solved in ${result.attempts || result.alreadySolved && 1} attempt(s)`
                  : `✗ Not yet — attempt ${result.attempts}`}
                {result.feedback && !result.correct && (
                  <div className="small" style={{ fontWeight: 400, marginTop: 4 }}>{result.feedback}</div>
                )}
              </div>
            )}
          </div>
        )}

        {history && history.grid.length > 0 && (
          <div className="card mt">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Your grid</h3>
              <button className="btn btn-ghost btn-sm" onClick={share}>
                {copied ? "Copied ✓" : "Share (spoiler-free)"}
              </button>
            </div>
            <div className="drop-grid mt" role="list" aria-label="Your Daily Drop history">
              {history.grid.map((g) => (
                <span key={g.day} className="drop-day" role="listitem"
                  aria-label={`${g.day}, ${g.mark}, ${g.attempts} attempt(s)`}>
                  {g.mark}
                </span>
              ))}
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>
              🟩 first try · 🟡 within 3 · 🟧 harder · 🔴 missed today
            </p>
          </div>
        )}
      </div>
    </>
  );
}
