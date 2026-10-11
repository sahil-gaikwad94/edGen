// Session + tiny API client. All calls are relative — the Next dev server
// proxies /api/* to the FastAPI backend (see next.config.js).

export function getSession() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem("edgen.session") || "null");
  } catch {
    return null;
  }
}

export function setSession(session) {
  localStorage.setItem("edgen.session", JSON.stringify(session));
  return session;
}

let sessionCreation = null;

export async function ensureSession(patch = {}) {
  const existing = getSession();
  if (existing?.userId) return existing;

  // React Strict Mode can mount a page effect twice in development. Share one
  // creation request so both mounts keep the same anonymous learner id.
  if (!sessionCreation) {
    sessionCreation = (async () => {
      const r = await fetch("/api/v1/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!r.ok) throw new Error(`Could not create session (${r.status})`);
      const data = await r.json();
      return setSession({ userId: data.user_id, ...patch });
    })();
  }

  const pending = sessionCreation;
  try {
    return await pending;
  } finally {
    if (sessionCreation === pending) sessionCreation = null;
  }
}

function headers(session, extra = {}) {
  const h = { "Content-Type": "application/json", ...extra };
  if (session?.userId) h["X-User-Id"] = session.userId;
  return h;
}

export async function api(path, { method = "GET", body, session, idempotencyKey, query } = {}) {
  const qs = query
    ? "?" + new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null))
    : "";
  const res = await fetch(`/api${path}${qs}`, {
    method,
    headers: headers(session, idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail?.[0]?.msg || (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail));
    } catch {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function newIdempotencyKey() {
  return (crypto.randomUUID?.() || String(Math.random()).slice(2)) + Date.now();
}
