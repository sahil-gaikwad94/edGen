"""Lesson service: cache-first core/delta (architecture §6) + reasoning diff (§11)."""
from __future__ import annotations

import sqlite3
from typing import Any

from edgen_lesson_ir import cache_key

from ..content import get_content
from ..model_gateway import ModelGateway

_gateway = ModelGateway()


def get_lesson(conn: sqlite3.Connection, user_id: str, node_id: str,
               lang: str = "en", depth: str = "standard", style: str = "default") -> dict[str, Any]:
    content = get_content()
    try:
        node = content.graph.get(node_id)
    except KeyError:
        return {"status": "not_found", "node_id": node_id}

    authored = content.authored_lesson(node_id)
    if authored is not None:
        # cache hit → logged (cost metering day one; hits cost $0)
        _gateway.log_call(conn, feature="lesson_core", tier="T0", model="authored",
                          cost_usd=0.0, cache_hit=True, user_id=user_id)
        return {
            "status": "ready",
            "provenance": "authored",
            "cache": {"key": cache_key(node.subject, node_id, lang, depth, style, authored.core_version),
                      "hit": True},
            "lesson": authored.model_dump(),
        }

    # degrade ladder: serve a draft scaffold rather than nothing
    scaffold = content.scaffold_lesson(node_id)
    _gateway.log_call(conn, feature="lesson_core", tier="T0", model="scaffold",
                      cost_usd=0.0, cache_hit=False, user_id=user_id)
    if scaffold is None:
        return {"status": "queued", "node_id": node_id}
    return {
        "status": "ready",
        "provenance": "scaffold",
        "cache": {"key": cache_key(node.subject, node_id, lang, depth, style, 0), "hit": False},
        "lesson": scaffold.model_dump(),
    }


# --- Reasoning-Diff (typed steps, W1) ---------------------------------------

def _norm(s: str) -> str:
    return " ".join(s.lower().replace("→", "->").replace("≤", "<=").split())


def reasoning_diff(learner_steps: list[str], oracle_steps: list[str]) -> dict[str, Any]:
    """LCS alignment over normalised steps → first divergence + violated line."""
    a = [_norm(s) for s in learner_steps]
    b = [_norm(s) for s in oracle_steps]
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(m):
            dp[i + 1][j + 1] = dp[i][j] + 1 if a[i] == b[j] else max(dp[i][j + 1], dp[i + 1][j])
    # walk back to find first learner step not matched
    i = j = 0
    divergence = None
    while i < n and j < m:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            if divergence is None:
                divergence = {"learner_step": i + 1, "your_text": learner_steps[i],
                              "oracle_at": j + 1, "oracle_text": oracle_steps[j] if j < m else None}
            i += 1
        else:
            j += 1
    if divergence is None and i < n:
        divergence = {"learner_step": i + 1, "your_text": learner_steps[i],
                      "oracle_at": j + 1, "oracle_text": oracle_steps[j] if j < m else "(oracle complete)"}
    return {
        "aligned": divergence is None,
        "first_divergence": divergence,
        "matched_steps": dp[n][m],
        "trust_label": "VERIFIED",  # diff facts come from code; wording is canned
    }
