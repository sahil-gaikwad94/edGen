import Link from "next/link";
import { useRouter } from "next/router";

export function Ring({ value = 0, size = 46 }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value || 0));
  return (
    <div className="ring" role="img" aria-label={`Readiness ${Math.round(pct * 100)} percent`} style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.13)" strokeWidth="5" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="#bba4ff" strokeWidth="5" strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
        />
      </svg>
      <div className="ring-label">{Math.round(pct * 100)}</div>
    </div>
  );
}

export default function Nav({ readiness }) {
  const router = useRouter();
  const path = router.pathname;
  const link = (href, label) => {
    const active = path === href || path.startsWith(href + "/");
    return (
      <Link href={href} className={active ? "active" : ""} aria-current={active ? "page" : undefined}>
        {label}
      </Link>
    );
  };
  return (
    <nav className="nav" aria-label="Primary navigation">
      <div className="nav-inner">
        <Link href="/" className="logo">
          <span className="logo-mark">E</span> EdGen
        </Link>
        <div className="nav-links">
          {link("/today", "Today")}
          {link("/tree", "Skill tree")}
          {link("/syllabi", "Syllabi")}
          {link("/drop", "Daily Drop")}
        </div>
        <div className="nav-right">
          <span className="track-chip">GATE CSE · graph v0</span>
          {readiness != null && <Ring value={readiness} />}
        </div>
      </div>
    </nav>
  );
}
