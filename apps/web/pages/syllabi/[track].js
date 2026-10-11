import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Nav from "../../components/Nav";
import { api } from "../../lib/api";

function ModuleCard({ module, accent }) {
  return (
    <article className={`syllabus-module ${module.graph_subject ? "module-interactive" : ""}`}
      style={{ "--track-accent": accent }}>
      <div className="module-card-head">
        <div>
          <p className="module-kicker">MODULE · {String(module.hours).padStart(2, "0")} HOURS</p>
          <h3>{module.title}</h3>
        </div>
        {module.graph_subject ? (
          <Link className="module-live-tag" href="/tree">IN LIVE SKILL TREE ↗</Link>
        ) : (
          <span className="module-outline-tag">CURRICULUM</span>
        )}
      </div>
      <p className="module-summary">{module.summary}</p>
      <details className="module-details">
        <summary>{module.topics.length} topics and practice outcomes</summary>
        <ul className="topic-list">
          {module.topics.map((topic, i) => <li key={`${module.id}-${i}`}>{topic}</li>)}
        </ul>
        {module.practice?.length > 0 && (
          <div className="module-practice">
            <span className="eyebrow">APPLY IT</span>
            <ul>{module.practice.map((practice, i) => <li key={i}>{practice}</li>)}</ul>
          </div>
        )}
      </details>
    </article>
  );
}

export default function SyllabusDetail() {
  const router = useRouter();
  const { track } = router.query;
  const [syllabus, setSyllabus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!track) return;
    let alive = true;
    api(`/v1/syllabi/${track}`)
      .then((data) => { if (alive) setSyllabus(data); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [track]);

  const accent = syllabus?.track_id === "full_stack" ? "#69D7C5"
    : syllabus?.track_id === "ai" ? "#F7B36B"
      : syllabus?.track_id === "ml" ? "#B59CFF" : "#A78BFA";
  const interactive = syllabus?.experience_status === "partial";

  return (
    <>
      <Nav />
      <main className="container syllabus-detail" id="main-content" style={{ "--track-accent": accent }}>
        <div className="syllabus-breadcrumb"><Link href="/syllabi">← All syllabi</Link><span>/</span>{syllabus?.title || track}</div>
        {error && <div className="error-text" role="alert">{error}</div>}
        {!syllabus && !error && <p className="muted" role="status">Loading syllabus…</p>}

        {syllabus && (
          <>
            <section className="syllabus-detail-hero">
              <div className="eyebrow">{syllabus.goal_type === "exam" ? "EXAM PATHWAY" : "ROLE PATHWAY"} · CURRICULUM V1</div>
              <div className="detail-hero-grid">
                <div>
                  <h1>{syllabus.title}</h1>
                  <p className="detail-tagline">{syllabus.tagline}</p>
                  <p className="sub">{syllabus.description}</p>
                </div>
                <div className="syllabus-summary-card glass-card">
                  <span className={`track-status ${interactive ? "is-live" : "is-outline"}`}>
                    <span className="status-dot" />{interactive ? "INTERACTIVE SLICE LIVE" : "SYLLABUS LIVE"}
                  </span>
                  <div className="summary-stats">
                    <div><strong>{syllabus.phase_count}</strong><span>phases</span></div>
                    <div><strong>{syllabus.module_count}</strong><span>modules</span></div>
                    <div><strong>{syllabus.topic_count}</strong><span>topics</span></div>
                    <div><strong>{syllabus.estimated_hours}h</strong><span>study estimate</span></div>
                  </div>
                  {interactive ? (
                    <Link href="/tree" className="btn">Explore the live OS + DBMS tree →</Link>
                  ) : (
                    <span className="small muted">Adaptive lessons and practice for this track are staged next.</span>
                  )}
                </div>
              </div>
            </section>

            {syllabus.exam_structure && (
              <section className="exam-structure glass-card">
                <div>
                  <div className="eyebrow">EXAM FORMAT · VERIFY EACH CYCLE</div>
                  <h2>{syllabus.exam_structure.duration} · {syllabus.exam_structure.total_marks} marks</h2>
                  <p className="small muted">{syllabus.exam_structure.note}</p>
                </div>
                <div className="exam-section-pills">
                  {syllabus.exam_structure.sections.map((s) => (
                    <div key={s.id} className="exam-section-pill">
                      <strong>{s.marks}</strong><span>{s.title}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {syllabus.scope_note && (
              <aside className="scope-note"><span aria-hidden="true">ⓘ</span><p>{syllabus.scope_note}</p></aside>
            )}

            <div className="syllabus-toolbar syllabus-plan-toolbar">
              <div>
                <div className="eyebrow">THE LEARNING ROUTE</div>
                <h2>Curriculum map</h2>
              </div>
              <span className="small muted">Sequenced foundations → applied practice → capstone</span>
            </div>

            <div className="phase-list">
              {syllabus.phases.map((phase, phaseIndex) => (
                <section key={phase.id} className="syllabus-phase">
                  <div className="phase-rail">
                    <span className="phase-number">{String(phaseIndex + 1).padStart(2, "0")}</span>
                    {phaseIndex < syllabus.phases.length - 1 && <span className="phase-line" />}
                  </div>
                  <div className="phase-content">
                    <div className="phase-heading">
                      <div><p className="module-kicker">PHASE {String(phaseIndex + 1).padStart(2, "0")}</p><h2>{phase.title}</h2></div>
                      <span className="phase-mod-count">{phase.modules.length} modules · {phase.modules.reduce((total, module) => total + module.hours, 0)}h</span>
                    </div>
                    <p className="phase-summary">{phase.summary}</p>
                    <div className="module-grid">
                      {phase.modules.map((module) => <ModuleCard key={module.id} module={module} accent={accent} />)}
                    </div>
                  </div>
                </section>
              ))}
            </div>

            <footer className="syllabus-footer glass-card">
              <div>
                <div className="eyebrow">YOUR NEXT STEP</div>
                <h2>{interactive ? "Start with your current Twin" : "Explore another path"}</h2>
                <p className="small muted">
                  {interactive
                    ? "The live learner graph covers 105 OS + DBMS concepts today; this syllabus also maps the rest of the exam."
                    : "The whole syllabus is available to browse. Interactive track learning will be activated as graph nodes, lessons, and graders are verified."}
                </p>
              </div>
              <Link href={interactive ? "/today" : "/syllabi"} className="btn">
                {interactive ? "Open Today →" : "Browse all syllabi →"}
              </Link>
            </footer>
          </>
        )}
      </main>
    </>
  );
}
