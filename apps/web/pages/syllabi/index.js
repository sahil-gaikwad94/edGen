import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Nav from "../../components/Nav";
import { api } from "../../lib/api";

export default function SyllabiIndex() {
  const [syllabi, setSyllabi] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api("/v1/syllabi"), api("/v1/tracks")])
      .then(([s, t]) => {
        setSyllabi(s.syllabi || []);
        setTracks(t.tracks || []);
      })
      .catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const byId = new Map(tracks.map((t) => [t.id, t]));
    return syllabi.filter((s) => !q || `${s.title} ${s.tagline} ${s.description} ${s.audience || ""} ${s.outcome || ""}`.toLowerCase().includes(q))
      .map((s) => ({ ...s, track: byId.get(s.track_id) }));
  }, [syllabi, tracks, query]);

  return (
    <>
      <Nav />
      <main className="container syllabus-index" id="main-content">
        <section className="syllabus-hero">
          <div className="eyebrow">THE EDGEN CURRICULUM LIBRARY</div>
          <h1>Four paths.<br /><span>Clear coverage.</span></h1>
          <p className="sub">
            Complete, sequenced syllabi for exam preparation and role readiness — with honest labels for what is interactive today.
          </p>
          <div className="curriculum-legend">
            <span><i className="legend-dot legend-interactive" /> GATE CSE interactive slice live</span>
            <span><i className="legend-dot legend-outline" /> Syllabus published; interactive track staged</span>
          </div>
        </section>

        <div className="syllabus-toolbar">
          <div>
            <div className="eyebrow">CHOOSE YOUR DESTINATION</div>
            <h2>Curriculum paths</h2>
          </div>
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search tracks" aria-label="Search syllabi" />
          </label>
        </div>

        {error && <p className="error-text" role="alert">{error}</p>}
        {!syllabi.length && !error && <p className="muted" role="status">Loading the curriculum library…</p>}
        <div className="syllabi-grid">
          {filtered.map((s) => {
            const live = s.experience_status === "partial";
            return (
              <Link key={s.track_id} href={`/syllabi/${s.track_id}`} className={`syllabus-tile ${live ? "tile-live" : ""}`}
                style={{ "--track-accent": s.track?.accent || "#ae9cff" }}>
                <div className="tile-topline">
                  <span className="track-icon" aria-hidden="true">{s.track_id === "gate_cse" ? "⌘" : s.title.slice(0, 1)}</span>
                  <span className={`track-status ${live ? "is-live" : "is-outline"}`}>
                    <span className="status-dot" />{live ? "INTERACTIVE SLICE LIVE" : "SYLLABUS LIVE"}
                  </span>
                </div>
                <div className="tile-title">
                  <h3>{s.title}</h3>
                  <span className="tile-arrow" aria-hidden="true">↗</span>
                </div>
                <p className="tile-tagline">{s.tagline}</p>
                <p className="small muted">{s.description}</p>
                <div className="tile-metrics">
                  <span><b>{s.phase_count}</b><small>phases</small></span>
                  <span><b>{s.module_count}</b><small>modules</small></span>
                  <span><b>{s.topic_count}</b><small>topics</small></span>
                  <span><b>{s.estimated_hours}h</b><small>estimated</small></span>
                </div>
                <span className="tile-open">View complete syllabus <span aria-hidden="true">→</span></span>
              </Link>
            );
          })}
        </div>
        {syllabi.length > 0 && filtered.length === 0 && <div className="empty-state">No curriculum matches “{query}”.</div>}
        <p className="syllabus-footnote">
          Role paths are curated skill maps, not certification or hiring guarantees. GATE scope, dates, and exam rules should be checked against the current official brochure.
        </p>
      </main>
    </>
  );
}
