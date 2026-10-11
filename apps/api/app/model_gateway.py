"""Model gateway: routing, budgets, cost metering, cassette replay.

W0 ships with no live model credentials: every call either hits a recorded
cassette (replay) or reports the degradation ladder. Cost is logged per feature
from day one — this is the number that decides whether "free" is sustainable
(SystemsDesign §9).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from . import config
from .db import now_iso

TIERS = {"T0": "tiny classify/route/extract", "T1": "mid open-source draft/delta",
         "T2": "frontier verification/offline authoring"}


class GatewayDisabled(Exception):
    pass


class ModelGateway:
    def __init__(self, cassette_dir: Path | None = None):
        self.cassette_dir = Path(cassette_dir or (config.CONTENT_DIR / "cassettes"))
        self._lock = threading.Lock()

    def replay(self, cassette: str, prompt_hash: str) -> dict[str, Any] | None:
        path = self.cassette_dir / f"{cassette}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return data.get(prompt_hash)

    def log_call(
        self,
        conn: sqlite3.Connection,
        *,
        feature: str,
        tier: str = "T0",
        model: str = "none",
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        cache_hit: bool = False,
        user_id: str | None = None,
    ) -> None:
        conn.execute(
            "insert into model_call (ts, feature, tier, model, tokens_in, tokens_out, cost_usd, cache_hit, user_id)"
            " values (?,?,?,?,?,?,?,?,?)",
            (now_iso(), feature, tier, model, tokens_in, tokens_out, cost_usd, 1 if cache_hit else 0, user_id),
        )
        conn.commit()

    def complete(self, conn: sqlite3.Connection, *, feature: str, prompt: str, tier: str = "T1",
                 user_id: str | None = None) -> str | None:
        """Return a completion or None (caller follows the degrade ladder)."""
        import hashlib

        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        hit = self.replay(feature, prompt_hash)
        if hit is not None:
            self.log_call(conn, feature=feature, tier=tier, model="cassette", cost_usd=0.0,
                          cache_hit=True, user_id=user_id,
                          tokens_in=len(prompt) // 4, tokens_out=len(hit.get("text", "")) // 4)
            return hit["text"]
        # No cassette: log the miss so the metering pipeline stays exercised.
        self.log_call(conn, feature=feature, tier=tier, model="none", cost_usd=0.0,
                      cache_hit=False, user_id=user_id, tokens_in=len(prompt) // 4)
        return None


def cost_report(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "select feature, count(*) as calls, sum(cost_usd) as cost, sum(cache_hit) as hits"
        " from model_call group by feature order by feature"
    ).fetchall()
    total = conn.execute(
        "select coalesce(sum(cost_usd),0) as c, coalesce(sum(cache_hit),0) as h, count(*) as n from model_call"
    ).fetchone()
    return {
        "by_feature": [dict(r) for r in rows],
        "totals": {"cost_usd": total["c"], "calls": total["n"], "cache_hits": total["h"]},
        "daily_budget_usd": config.MODEL_DAILY_BUDGET_USD,
    }
