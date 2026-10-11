#!/usr/bin/env python3
"""Isolated end-to-end API smoke for the W1 core loop.

Usage: python scripts/smoke.py
Creates a temporary SQLite database, warms the published Foundry pools, and
runs onboarding → diagnostic → tree/plan → lesson → verified attempts →
Daily Drop → export/delete. No production or local data is touched.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for package_src in sorted((ROOT / "packages").glob("*/src")):
    sys.path.insert(0, str(package_src))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="edgen-smoke-") as tmp:
        tmp_path = Path(tmp)
        os.environ["EDGEN_ROOT"] = str(ROOT)
        os.environ["EDGEN_CONTENT"] = str(ROOT / "content")
        os.environ["EDGEN_DATA"] = str(tmp_path)
        os.environ["EDGEN_DB"] = str(tmp_path / "smoke.db")

        from fastapi.testclient import TestClient
        from edgen_foundry import get_generator
        from apps.api.app.db import connect, loads
        from apps.api.app.main import app

        def solved(instance_id: str):
            conn = connect()
            try:
                row = conn.execute(
                    "select generator_id, params from instance_pool where instance_id=?",
                    (instance_id,),
                ).fetchone()
                if row is None:
                    raise AssertionError(f"unknown smoke instance {instance_id}")
                params = loads(row["params"])
                gen = get_generator(row["generator_id"])
                return gen.answer_key(params, gen.solve_a(params))
            finally:
                conn.close()

        def check(resp, label: str):
            if resp.status_code >= 400:
                raise AssertionError(f"{label}: HTTP {resp.status_code}: {resp.text}")
            return resp.json()

        with TestClient(app) as client:
            health = check(client.get("/v1/healthz"), "health")
            assert health["ok"] and health["nodes"] >= 100
            session = check(client.post("/v1/session", json={
                "track": "gate_cse", "lens": "gate_cse", "goal_type": "exam",
                "goal_date": "2027-05-01", "minutes_per_day": 45, "onboarded": True,
            }), "create session")
            headers = {"X-User-Id": session["user_id"]}
            check(client.patch("/v1/session", headers=headers, json={
                "track": "gate_cse", "lens": "gate_cse", "goal_type": "exam",
                "goal_date": "2027-05-01", "minutes_per_day": 45, "onboarded": True,
            }), "save onboarding")

            diagnostic = check(client.post("/v1/diagnostic/start", headers=headers), "diagnostic start")
            assert diagnostic["total"] == 8 and diagnostic["status"] == "in_progress"
            assert all(len(item["hints"]) == 4 for item in diagnostic["items"])
            for idx, item in enumerate(diagnostic["items"]):
                out = check(client.post("/v1/diagnostic/answer", headers=headers, json={
                    "idx": idx, "answer": solved(item["instance_id"]), "confidence": 75,
                }), f"diagnostic answer {idx + 1}")
            assert out["status"] == "complete" and out["plan"]["items"]

            tree = check(client.get("/v1/tree?lens=gate_cse", headers=headers), "skill tree")
            assert tree["counts"]["frontier"] > 0 and tree["readiness"] is not None
            plan = check(client.get("/v1/plan/today?lens=gate_cse", headers=headers), "today plan")
            assert len(plan["items"]) >= 3
            lesson = check(client.get("/v1/lessons/os.scheduling.rr", headers=headers), "lesson")
            assert lesson["provenance"] == "authored" and len(lesson["lesson"]["blocks"]) > 0

            problem = check(client.get("/v1/problems/os.cpu_scheduling?bucket=2", headers=headers), "problem")
            assert "answer" not in problem and "params" not in problem
            bad = check(client.post("/v1/attempts", headers=headers, json={
                "generator_id": problem["generator_id"], "instance_id": problem["instance_id"],
                "answer": "definitely-not-the-answer", "confidence": 25, "hint_level": 1,
                "steps": ["start with an incorrect claim"], "lens": "gate_cse",
            }), "incorrect attempt")
            assert bad["verdict"]["correct"] is False
            good = check(client.post("/v1/attempts", headers=headers, json={
                "generator_id": problem["generator_id"], "instance_id": problem["instance_id"],
                "answer": solved(problem["instance_id"]), "confidence": 90,
                "steps": ["compute the schedule", "calculate waiting times"], "lens": "gate_cse",
            }), "correct attempt")
            assert good["verdict"]["correct"] and good["verdict"]["trust_label"] == "VERIFIED"
            assert good["reasoning_diff"] is not None and good["plan"]["items"]

            drop = check(client.get("/v1/daily-drop", headers=headers), "daily drop")
            drop_result = check(client.post("/v1/daily-drop/answer", headers=headers, json={
                "answer": solved(drop["instance_id"]), "confidence": 80,
            }), "daily drop answer")
            history = check(client.get("/v1/daily-drop/history", headers=headers), "drop history")
            assert drop_result["correct"] and history["grid"] and history["share_text"]

            export = check(client.get("/v1/me/data", headers=headers), "data export")
            assert export["attempt"]
            deleted = check(client.delete("/v1/me/data", headers=headers), "data delete")
            assert deleted["deleted"] > 0

        print("PASS  onboarding + track/goal")
        print("PASS  placement diagnostic (8 verified items)")
        print("PASS  skill tree + 3-item Today plan")
        print("PASS  authored lesson + trust badges")
        print("PASS  wrong/correct verified practice + Twin + re-plan")
        print("PASS  Daily Drop + share grid")
        print("PASS  learner data export + delete")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
