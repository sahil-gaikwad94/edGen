import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Nav from "../components/Nav";
import { api, ensureSession, getSession, setSession } from "../lib/api";

function TrackCard({ t }) {
  const live = t.status === "active";
  const syllabus = t.syllabus || {};
  return (
    <article className={`track-card card ${live ? "track-live" : ""}`} style={{ "--track-accent": t.accent || "#ae9cff" }}>
      <div className="track-card-head">
        <span className="track-icon" aria-hidden="true">{t.id === "gate_cse" ? "⌘" : t.title.slice(0, 1)}</span>
        <span className={`track-status ${live ? "is-live" : "is-outline"}`}>
          <span className="status-dot" />{live ? "INTERACTIVE SLICE LIVE" : "SYLLABUS LIVE"}
        </span>
      </div>
      <div className="track-card-title-row">
        <div>
          <h3>{t.title}</h3>
          <p className="track-goal">{t.goal_type === "exam" ? "EXAM READINESS" : "ROLE READINESS"}</p>
        </div>
        <span className="track-arrow" aria-hidden="true">↗</span>
      </div>
      <p className="small muted">{t.blurb}</p>
      <div className="track-metrics">
        <span><strong>{syllabus.phase_count || 0}</strong> phases</span>
        <span><strong>{syllabus.module_count || 0}</strong> modules</span>
        <span><strong>{syllabus.topic_count || 0}</strong> topics</span>
      </div>
      {live && <div className="track-live-note">{t.graph_nodes} interactive concepts · verified practice</div>}
      <Link href={`/syllabi/${t.id}`} className="track-link">
        Explore the full syllabus <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}

export default function Home() {
  const router = useRouter();
  const [tracks, setTracks] = useState([]);
  const [selectedTrack, setSelectedTrack] = useState("gate_cse");
  const [session, setSessionState] = useState(null);
  const [goalDate, setGoalDate] = useState("2027-05-01");
  const [minutes, setMinutes] = useState(45);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const selectedTrackInfo = tracks.find((t) => t.id === selectedTrack);
  const goalLabel = {
    exam: "Exam readiness",
    role: "Role readiness",
    mastery: "Mastery",
  }[selectedTrackInfo?.goal_type || "exam"];

  useEffect(() => {
    api("/v1/tracks").then((d) => setTracks(d.tracks)).catch(() => {});
    const s = getSession();
    setSessionState(s);
  }, []);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const trackInfo = tracks.find((t) => t.id === selectedTrack) || tracks.find((t) => t.status === "active");
      const trackId = trackInfo?.id || "gate_cse";
      const lens = trackInfo?.default_lens || trackInfo?.lenses?.[0] || trackId;
      const goalType = trackInfo?.goal_type || "exam";
      const onboarding = {
        track: trackId, lens, goal_type: goalType,
        goal_date: goalDate, minutes_per_day: minutes, onboarded: true,
      };
      const s = await ensureSession(onboarding);
      // Patch the server record if a local session already existed.
      await api("/v1/session", { method: "PATCH", session: s, body: onboarding });
      const onboardedSession = { ...s, ...onboarding };
      setSession(onboardedSession);
      await api("/v1/diagnostic/start", { method: "POST", session: onboardedSession });
      await router.push("/diagnostic");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="container" id="main-content">
        <section className="hero hero-home">
          <div className="hero-grid">
            <div className="hero-copy">
              <div className="eyebrow hero-eyebrow"><span className="eyebrow-signal" />A learning system that shows its work</div>
              <h1>Learn with a <span>twin</span> that shows its work.</h1>
              <p className="sub">
                EdGen turns your attempts into a skill model, then uses it to plan what to learn next.
                Browse complete curriculum maps for GATE CSE, Full Stack, Applied AI and ML. Today,
                the interactive learning loop is live for a focused slice of GATE CSE.
              </p>
              <div className="hero-proofline">
                <span><strong>105</strong> interactive concepts</span>
                <i aria-hidden="true" />
                <span>Operating systems + databases</span>
              </div>
              <div className="receipts" aria-label="Content trust signals">
                <span className="badge badge-verified">VERIFIED</span>
                <span className="badge badge-sourced">SOURCED</span>
                <span className="badge badge-model">MODEL</span>
                <span className="badge badge-judged">JUDGED</span>
              </div>
              <div className="hero-cta">
                {session ? (
                  <Link href="/today" className="btn">Continue learning <span aria-hidden="true">→</span></Link>
                ) : (
                  <button className="btn" onClick={start} disabled={busy}>
                    {busy ? "Preparing…" : "Take the 10-minute placement"} <span aria-hidden="true">→</span>
                  </button>
                )}
                <Link href="/syllabi" className="btn btn-ghost">Explore all four syllabi</Link>
              </div>
              {error && <div className="error-text" role="alert">{error}</div>}
            </div>

            <aside className="hero-visual" aria-labelledby="coverage-card-title">
              <div className="visual-glow" />
              <div className="twin-card">
                <div className="twin-card-top">
                  <div className="twin-avatar" aria-hidden="true">⌘</div>
                  <div className="twin-label">
                    <strong id="coverage-card-title">GATE CSE · interactive slice</strong>
                    <small>GRAPH V0 · OS + DBMS</small>
                  </div>
                  <span className="track-status is-live"><span className="status-dot" />PARTIAL</span>
                </div>
                <div className="twin-graph-meta">
                  <span>LIVE CONCEPT MAP</span><span>105 NODES</span>
                </div>
                <div className="skill-orbit" aria-hidden="true">
                  <span className="orbit-line one" /><span className="orbit-line two" />
                  <span className="skill-node n1"><i />Operating systems</span>
                  <span className="skill-node n2"><i />Scheduling</span>
                  <span className="skill-node n3"><i />Databases</span>
                  <span className="skill-node n4"><i />Normalization</span>
                </div>
                <div className="hero-twin-metrics">
                  <div><strong>55</strong><span>OS concepts</span></div>
                  <div className="metric-divider" aria-hidden="true" />
                  <div><strong>50</strong><span>DBMS concepts</span></div>
                  <span className="adaptive-tag"><span className="live-indicator" />ADAPTIVE LOOP</span>
                </div>
                <div className="twin-claim"><span aria-hidden="true">✓</span> Generated practice answers are computed by code.</div>
              </div>
              <div className="floating-proof"><span>CURRICULUM LIBRARY</span>4 tracks · ready to explore</div>
            </aside>
          </div>
        </section>

        {!session && (
          <section className="card" style={{ maxWidth: 560 }}>
            <h2>Set your goal</h2>
            <p className="small muted">
              Your plan adapts to one learner model. The live interactive graph currently covers OS + DBMS for GATE CSE; all four syllabus maps are ready to explore.
            </p>
            <div className="field">
              <label htmlFor="learning-track">Learning track</label>
              <select id="learning-track" value={selectedTrack} onChange={(e) => setSelectedTrack(e.target.value)}>
                {tracks.filter((t) => t.status === "active").map((t) => (
                  <option key={t.id} value={t.id}>{t.title} · learning loop live</option>
                ))}
                {tracks.filter((t) => t.status !== "active").map((t) => (
                  <option key={t.id} value={t.id} disabled>{t.title} · syllabus published</option>
                ))}
              </select>
              <div className="small muted">
                {selectedTrackInfo?.blurb || "GATE CSE interactive learning is live; all four curriculum maps are available to browse."}
              </div>
            </div>
            <div className="field">
              <label htmlFor="goal-type">Goal type</label>
              <input id="goal-type" value={goalLabel} readOnly />
              <div className="small muted">The track sets the goal lens. Set a target date and daily study budget below.</div>
            </div>
            <div className="field">
              <label htmlFor="goal-date">Exam / target date</label>
              <input id="goal-date" type="date" value={goalDate} onChange={(e) => setGoalDate(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="daily-minutes">Minutes per day</label>
              <select id="daily-minutes" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
                <option value={30}>30 — commute sprints</option>
                <option value={45}>45 — the standard plan</option>
                <option value={60}>60 — exam-season mode</option>
              </select>
            </div>
            <button className="btn" onClick={start} disabled={busy}>
              {busy ? "Preparing…" : "Start my GATE CSE learning loop"}
            </button>
          </section>
        )}

        <section className="mt">
          <h2>Four curriculum paths</h2>
          <div className="grid grid-2" style={{ marginTop: 12 }}>
            {tracks.map((t) => <TrackCard key={t.id} t={t} />)}
          </div>
        </section>

        <section className="card mt">
          <h2>The loop</h2>
          <div className="grid grid-3" style={{ marginTop: 10 }}>
            <div><strong>1 · Diagnose</strong><p className="small muted">8 verified questions place your Twin.</p></div>
            <div><strong>2 · Learn</strong><p className="small muted">Cache-first lessons with receipts, not vibes.</p></div>
            <div><strong>3 · Practice</strong><p className="small muted">Answers from two independent solvers agreeing.</p></div>
            <div><strong>4 · Diff</strong><p className="small muted">See the exact step your reasoning diverged.</p></div>
            <div><strong>5 · Re-plan</strong><p className="small muted">Today re-optimises after every attempt.</p></div>
            <div><strong>6 · Share</strong><p className="small muted">Daily Drop — one puzzle, spoiler-free grid.</p></div>
          </div>
        </section>

        <div className="footer">
          Working build · graph v0 (OS + DBMS) · <span className="mono">W0 → W1 phase 1</span> —
          all five Problem Foundry generators differential-verified on 10,000 seeds each.
          <div style={{ marginTop: 8 }}>EdGen is independent and is not affiliated with GATE, the IITs, or any exam authority.</div>
        </div>
      </main>
    </>
  );
}
