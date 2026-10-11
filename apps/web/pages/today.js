import { useEffect, useState } from "react";
import Link from "next/link";
import Nav from "../components/Nav";
import { api, ensureSession } from "../lib/api";

export default function Today() {
  const [session, setSessionState] = useState(null);
  const [plan, setPlan] = useState(null);
  const [tree, setTree] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  async function load(s) {
    try {
      const [p, t] = await Promise.all([
        api("/v1/plan/today", { session: s, query: { lens: "gate_cse" } }),
        api("/v1/tree", { session: s, query: { lens: "gate_cse" } }),
      ]);
      setPlan(p);
      setTree(t);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    (async () => {
      const s = await ensureSession();
      setSessionState(s);
      await load(s);
    })();
  }, []);

  async function refresh() {
    setRefreshing(true);
    try {
      const p = await api("/v1/plan/refresh", { method: "POST", session, query: { lens: "gate_cse" } });
      setPlan(p);
    } catch (e) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  }

  const titleOf = (id) => tree?.nodes.find((n) => n.id === id)?.title || id;
  const hrefFor = (it) =>
    it.type === "practice" || it.type === "repair" || it.type === "review"
      ? `/practice/${it.generator_id || "os.cpu_scheduling"}?node=${it.node_id}`
      : `/learn/${it.node_id}`;

  return (
    <>
      <Nav readiness={tree?.readiness} />
      <div className="narrow" style={{ paddingTop: 26 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 10 }}>
          <div>
            <h1 style={{ marginBottom: 2 }}>Today</h1>
            <div className="muted small mono">{plan?.day} · {plan?.total_minutes} min planned</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={refreshing}>
            {refreshing ? "Re-optimising…" : "Re-plan"}
          </button>
        </div>

        {error && <div className="error-text" role="alert">{error}</div>}

        {plan && plan.items.length === 0 && (
          <div className="card mt">
            <p>Nothing servable right now — finish a diagnostic or check back after review is due.</p>
          </div>
        )}

        <div className="mt">
          {plan?.items.map((it, i) => (
            <div className="card plan-card" key={`${it.node_id}-${i}`}>
              <span className={`plan-kind kind-${it.type}`}>{it.type.toUpperCase()}</span>
              <div style={{ flex: 1 }}>
                <h3 style={{ marginBottom: 4 }}>{titleOf(it.node_id)}</h3>
                <div className="mono small muted">{it.node_id}</div>
                <div className="plan-reason" style={{ marginTop: 6 }}>{it.reason}</div>
                <div className="plan-foot">
                  <span className="plan-min">
                    ~{it.est_min} min · p={it.propensity?.toFixed?.(3) ?? it.propensity} · {it.policy_id}
                  </span>
                  <Link href={hrefFor(it)} className="btn btn-sm">
                    {it.type === "lesson" ? "Start lesson →" : "Start practice →"}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

        {plan && (
          <div className="card mt">
            <strong className="small">Why this plan?</strong>
            <p className="small muted" style={{ marginTop: 6 }}>
              Greedy gain/cost over your frontier and due reviews, prerequisites enforced, clusters interleaved,
              ~15% exploration — every item logs <span className="mono">policy_id + propensity</span> so the
              Twin can be evaluated offline (ADR 9).
            </p>
            <div className="small mono muted" style={{ marginTop: 6 }}>
              frontier: {plan.log?.frontier?.length ?? "—"} · reviews due: {plan.log?.review_due?.length ?? "—"} ·
              explore: {plan.log?.explore || "—"}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
