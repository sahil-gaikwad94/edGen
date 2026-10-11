// Lesson block renderer (architecture §6: trust badges on every item)
// + template visualizers (ADR 6: templates before generated animation code).

function Badge({ badge }) {
  if (!badge) return null;
  return <span className={`badge badge-${badge.toLowerCase()}`}>{badge}</span>;
}

function receiptNote(b) {
  const r = b.receipt;
  if (!r) return null;
  if (r.kind === "source_span")
    return (
      <div className="receipt-note">
        ↳ source span {r.source_id}:{r.span?.[0]}–{r.span?.[1]} · {r.license}
      </div>
    );
  if (r.kind === "executed" || r.kind === "tests")
    return <div className="receipt-note">↳ {r.detail}</div>;
  return null;
}

function Gantt({ spec }) {
  const segs = spec.segments || [];
  const end = Math.max(...segs.map((s) => s.to), 1);
  const pids = [...new Set(segs.map((s) => s.pid))];
  const colors = ["#9278f2", "#55c99a", "#dc9650", "#bb8cff", "#74a9ff"];
  const w = 560, h = 46 + (spec.quantum ? 16 : 0);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: "100%" }}>
      {segs.map((s, i) => {
        const x = (s.from / end) * (w - 20) + 10;
        const bw = Math.max(3, ((s.to - s.from) / end) * (w - 20));
        const color = colors[pids.indexOf(s.pid) % colors.length];
        return (
          <g key={i}>
            <rect x={x} y={8} width={bw} height={26} rx="5" fill={color} opacity="0.9" />
            <text x={x + bw / 2} y={25} textAnchor="middle" fill="#fff" fontSize="11.5" fontWeight="700">
              {s.pid}
            </text>
            <text x={x} y={46} fill="#9298aa" fontSize="9.5" fontFamily="monospace">{s.from}</text>
          </g>
        );
      })}
      <text x={w - 12} y={25} fill="#9298aa" fontSize="10" textAnchor="end" fontFamily="monospace">{end}</text>
    </svg>
  );
}

function Frames({ spec }) {
  const n = spec.frames || 3;
  return (
    <div>
      <div style={{ display: "flex", gap: 8 }}>
        {Array.from({ length: n }).map((_, i) => (
          <div key={i} style={{
            width: 54, height: 44, border: "1.5px dashed rgba(255,255,255,.28)", borderRadius: 8,
            display: "grid", placeItems: "center", color: "#8f93a3", fontFamily: "monospace", fontSize: 12,
          }}>
            {spec.algorithm || ""} {i + 1}
          </div>
        ))}
      </div>
      <div className="small muted" style={{ marginTop: 8 }}>{spec.caption}</div>
    </div>
  );
}

function FdGraph({ spec }) {
  const nodes = spec.nodes || [];
  const w = 460, h = 130;
  const pos = {};
  nodes.forEach((n, i) => {
    pos[n] = { x: 90 + i * ((w - 160) / Math.max(1, nodes.length - 1)), y: 65 };
  });
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: "100%" }}>
        {(spec.edges || []).map((e, i) => {
          const a = pos[e.from], b = pos[e.to];
          if (!a || !b) return null;
          const dx = b.x - a.x, dy = b.y - a.y;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const ux = dx / len, uy = dy / len;
          const x1 = a.x + ux * 30, y1 = a.y + uy * 30;
          const x2 = b.x - ux * 34, y2 = b.y - uy * 34;
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#bba5ff" strokeWidth="2" />
              <polygon points={`${x2},${y2} ${x2 - ux * 8 - uy * 4},${y2 - uy * 8 + ux * 4} ${x2 - ux * 8 + uy * 4},${y2 - uy * 8 - ux * 4}`} fill="#bba5ff" />
              <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 7} textAnchor="middle" fontSize="11" fill="#9298aa" fontFamily="monospace">
                {e.label}
              </text>
            </g>
          );
        })}
        {nodes.map((n) => (
          <g key={n}>
            <circle cx={pos[n].x} cy={pos[n].y} r="26" fill="rgba(187,165,255,.16)" stroke="#bba5ff" strokeWidth="1.8" />
            <text x={pos[n].x} y={pos[n].y + 5} textAnchor="middle" fontWeight="700" fontSize="14" fill="#f5f3fa">
              {n}
            </text>
          </g>
        ))}
      </svg>
      <div className="small muted">{spec.caption}</div>
    </div>
  );
}

function DiskTrack({ spec }) {
  const w = 560, x = (c) => 10 + (c / 199) * (w - 20);
  return (
    <div>
      <svg viewBox={`0 0 ${w} 96`} style={{ maxWidth: "100%" }}>
        <line x1="10" y1="58" x2={w - 10} y2="58" stroke="#5d6578" strokeWidth="2" />
        {[0, 50, 100, 150, 199].map((c) => (
          <g key={c}>
            <line x1={x(c)} y1="54" x2={x(c)} y2="62" stroke="#5d6578" />
            <text x={x(c)} y="78" textAnchor="middle" fontSize="10" fill="#9298aa" fontFamily="monospace">{c}</text>
          </g>
        ))}
        {(spec.requests || []).map((c) => (
          <circle key={c} cx={x(c)} cy="58" r="4" fill="#bba5ff" />
        ))}
        {spec.head != null && (
          <g>
            <line x1={x(spec.head)} y1="24" x2={x(spec.head)} y2="58" stroke="#b42318" strokeWidth="2" />
            <circle cx={x(spec.head)} cy="22" r="6" fill="#b42318" />
            <text x={x(spec.head)} y="14" textAnchor="middle" fontSize="10.5" fontWeight="700" fill="#b42318" fontFamily="monospace">
              head {spec.head}
            </text>
          </g>
        )}
        <text x="10" y="92" fontSize="11" fill="#9298aa" fontFamily="monospace">
          {spec.algorithm}: {(spec.order || []).join(" → ")}
        </text>
      </svg>
    </div>
  );
}

function StateCycle({ spec }) {
  const states = spec.states || [];
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
        {states.map((s, i) => (
          <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{
              padding: "5px 12px", borderRadius: 999, background: "rgba(187,165,255,.16)",
              border: "1.5px solid rgba(187,165,255,.6)", fontSize: 13, fontWeight: 600,
            }}>{s}</span>
            {i < states.length - 1 && <span className="muted">→</span>}
          </span>
        ))}
      </div>
      <div className="small muted" style={{ marginTop: 8 }}>{spec.caption}</div>
    </div>
  );
}

function Viz({ block }) {
  const t = block.template;
  if (t === "gantt") return <Gantt spec={block.spec} />;
  if (t === "frames") return <Frames spec={block.spec} />;
  if (t === "fd_graph") return <FdGraph spec={block.spec} />;
  if (t === "disk_track") return <DiskTrack spec={block.spec} />;
  if (t === "state_cycle") return <StateCycle spec={block.spec} />;
  return <pre className="small mono">{JSON.stringify(block.spec, null, 2)}</pre>;
}

export default function Blocks({ lesson }) {
  return (
    <div>
      {lesson.blocks.map((b) => {
        if (b.type === "viz") {
          return (
            <div key={b.id} className="lblock lblock-proof">
              <Viz block={b} />
            </div>
          );
        }
        if (b.type === "check") {
          return (
            <div key={b.id} className="lblock lblock-check">
              <Badge badge={b.badge} />
              <p>{b.prompt}</p>
              <a className="btn btn-sm" href={`/practice/${b.foundry}`}>
                Practice with verified code →
              </a>
            </div>
          );
        }
        if (b.type === "lab") {
          return (
            <div key={b.id} className="lblock lblock-lab">
              <Badge badge={b.badge} />
              <div style={{ marginTop: 6 }}>{b.starter}</div>
            </div>
          );
        }
        return (
          <div key={b.id} className={`lblock lblock-${b.type}`}>
            <Badge badge={b.badge} />
            <p dangerouslySetInnerHTML={{
              __html: (b.text || "")
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                .replace(/`([^`]+)`/g, "<code>$1</code>")
                .replace(/\n/g, "<br/>"),
            }} />
            {receiptNote(b)}
          </div>
        );
      })}
    </div>
  );
}
