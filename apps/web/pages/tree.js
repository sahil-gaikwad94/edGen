import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Nav from "../components/Nav";
import { api, ensureSession } from "../lib/api";

const STATE_LABEL = {
  mastered: "MASTERED",
  frontier: "LEARN NOW",
  remediation: "NEEDS REPAIR",
  locked: "LOCKED",
};

export default function Tree() {
  const [session, setSessionState] = useState(null);
  const [tree, setTree] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      const s = await ensureSession();
      setSessionState(s);
      try {
        setTree(await api("/v1/tree", { session: s, query: { lens: "gate_cse" } }));
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const byTopic = useMemo(() => {
    if (!tree) return [];
    const map = new Map();
    for (const n of tree.nodes) {
      if (!map.has(n.topic)) map.set(n.topic, []);
      map.get(n.topic).push(n);
    }
    return [...map.entries()].sort((a, b) => {
      const order = (t) => (t.startsWith("os.") ? 0 : 1);
      return order(a[0]) - order(b[0]) || a[0].localeCompare(b[0]);
    });
  }, [tree]);

  return (
    <>
      <Nav readiness={tree?.readiness} />
      <div className="container" style={{ paddingTop: 26 }}>
        {error && <div className="error-text" role="alert">{error}</div>}
        {tree && (
          <>
            <div className="card">
              <div className="readiness-bar">
                <div>
                  <div className="mono" style={{ fontSize: "2.2rem", fontWeight: 750 }}>
                    {Math.round((tree.readiness || 0) * 100)}%
                  </div>
                  <div className="small muted">lens readiness · gate_cse · graph v{tree.graph_version}</div>
                </div>
                <div className="stat-row">
                  <div className="stat"><div className="v" style={{ color: "var(--accent)" }}>{tree.counts.frontier}</div><div className="k">frontier</div></div>
                  <div className="stat"><div className="v" style={{ color: "var(--verified)" }}>{tree.counts.mastered}</div><div className="k">mastered</div></div>
                  <div className="stat"><div className="v muted">{tree.counts.locked}</div><div className="k">locked</div></div>
                </div>
                <div style={{ marginLeft: "auto" }}>
                  <Link href="/today" className="btn btn-sm">Today&apos;s plan →</Link>
                </div>
              </div>
            </div>

            {byTopic.map(([topic, nodes]) => (
              <div key={topic}>
                <div className="topic-head">{topic}</div>
                <div className="grid grid-3">
                  {nodes.map((n) => {
                    const clickable = n.state !== "locked";
                    const inner = (
                      <>
                        <div className="node-title">{n.title}</div>
                        <div className="mini-bar"><div style={{ width: `${Math.round(n.m_eff * 100)}%` }} /></div>
                        <div className="node-meta">
                          <span className="node-state">{STATE_LABEL[n.state]}{n.review_due ? " · REVIEW" : ""}</span>
                          <span className="mono small muted">{Math.round(n.m_eff * 100)}% · {n.est_minutes}m</span>
                        </div>
                        {n.generators.length > 0 && n.state !== "locked" && (
                          <span className="badge badge-verified" style={{ alignSelf: "start" }}>PRACTICE READY</span>
                        )}
                      </>
                    );
                    return (
                      <div key={n.id} className={`node node-${n.state}`}>
                        {clickable ? (
                          <Link href={`/learn/${n.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                            {inner}
                          </Link>
                        ) : inner}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </>
        )}
        {!tree && !error && <p className="muted">Loading your graph…</p>}
      </div>
    </>
  );
}
