import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Nav from "../../components/Nav";
import Blocks from "../../components/Blocks";
import { api, ensureSession } from "../../lib/api";

export default function LessonPage() {
  const router = useRouter();
  const { node } = router.query;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [genState, setGenState] = useState(null);
  const [genBusy, setGenBusy] = useState(false);

  useEffect(() => {
    if (!node) return;
    (async () => {
      const s = await ensureSession();
      try {
        setData(await api(`/v1/lessons/${node}`, { session: s }));
      } catch (e) {
        setError(e.message);
      }
    })();
  }, [node]);

  async function generateCore() {
    setGenBusy(true);
    try {
      const s = await ensureSession();
      const out = await api("/v1/runs", {
        method: "POST", session: s,
        body: { kind: "core_generation", node_id: node },
      });
      setGenState(out);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  if (error) return (<><Nav /><div className="narrow"><p className="error-text" role="alert">{error}</p></div></>);
  if (!data) return (<><Nav /><div className="narrow"><p className="muted">Loading lesson…</p></div></>);
  if (data.status === "not_found") {
    return (<><Nav /><div className="narrow"><p>Unknown node.</p><Link href="/tree">← Back to tree</Link></div></>);
  }

  const lesson = data.lesson;

  return (
    <>
      <Nav />
      <div className="narrow" style={{ paddingTop: 26 }}>
        <div className="small mono muted">
          <Link href="/tree">tree</Link> / {lesson.node_id}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 12, marginTop: 6 }}>
          <h1>{lesson.title}</h1>
          <span className={`badge ${lesson.review_status === "reviewed" ? "badge-verified" : "badge-model"}`}>
            {lesson.review_status === "reviewed" ? "REVIEWED CORE" : "DRAFT"}
          </span>
        </div>

        {data.provenance === "scaffold" && (
          <div className="scaffold-banner">
            Draft scaffold from the concept graph — the reviewed core is queued for batch authoring.
            {"  "}
            <button className="btn btn-ghost btn-sm" onClick={generateCore} disabled={genBusy}>
              {genBusy ? "Queueing…" : "Generate core"}
            </button>
            {genState && (
              <div className="mono small" style={{ marginTop: 6 }}>
                run {genState.run_id.slice(0, 8)} → {genState.status}
                {genState.payload?.note ? ` · ${genState.payload.note}` : ""}
              </div>
            )}
          </div>
        )}

        <div className="small mono muted" style={{ marginBottom: 8 }}>
          cache: <code>{data.cache.key}</code> · {data.cache.hit ? "HIT" : "MISS"}
        </div>

        <Blocks lesson={lesson} />

        <div className="mt" style={{ display: "flex", gap: 10 }}>
          <Link href="/today" className="btn btn-ghost btn-sm">← Today</Link>
          <Link href={`/practice/${lesson.blocks.find((b) => b.type === "check")?.foundry || "os.cpu_scheduling"}?node=${lesson.node_id}`}
            className="btn btn-sm">
            Practice this node →
          </Link>
        </div>
      </div>
    </>
  );
}
