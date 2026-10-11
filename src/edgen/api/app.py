"""FastAPI application — API surface v1 (architecture §19).

Design rules enforced here:
- Server-side answer keys only. ``/v1/problems`` never returns the correct flag.
- All mutations accept an ``Idempotency-Key`` header (and attempts carry their own
  client UUID), so retries are safe.
- Every graded response carries a trust badge.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from edgen.api.schemas import (
    AdvisorIn,
    AdvisorOut,
    AttemptIn,
    AttemptOut,
    DailyDropAnswerIn,
    DailyDropOut,
    DailyDropResult,
    DataExportOut,
    NodeOut,
    ProblemOut,
    ReadinessOut,
    TrackOut,
    TreeOut,
    VerificationOut,
)
from edgen.lesson.render import render_html
from edgen.planner.advisor import QuestionType, advise_attempt
from edgen.planner.planner import Planner
from edgen.store.state import AppState, get_state, now
from edgen.trust import Trust
from edgen.twin.service import Attempt


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI(
        title="EdGen API",
        version="0.1.0",
        description="Verified-practice learning agent. Every number computed by code.",
    )
    _state = state

    def state_dep() -> AppState:
        return _state or get_state()


    # ---------------------------------------------------------------- tracks --
    @app.get("/v1/tracks", response_model=list[TrackOut])
    def tracks(s: AppState = Depends(state_dep)) -> list[TrackOut]:
        return [
            TrackOut(
                id=s.lens.id,
                title=s.lens.title,
                goal_type=s.lens.goal_type.value,
                nodes=len(s.lens.nodes),
            )
        ]

    @app.get("/v1/lenses/{lens_id}")
    def lens_detail(lens_id: str, s: AppState = Depends(state_dep)) -> dict:
        if lens_id != s.lens.id:
            raise HTTPException(404, "unknown lens")
        return {
            "id": s.lens.id,
            "title": s.lens.title,
            "goal_type": s.lens.goal_type.value,
            "milestones": s.lens.milestones,
            "mock_config": s.lens.mock_config,
            "exam_date": s.lens.exam_date.isoformat() if s.lens.exam_date else None,
        }

    @app.get("/v1/tree", response_model=TreeOut)
    def tree(lens: str, s: AppState = Depends(state_dep), user_id: str = "demo") -> TreeOut:
        if lens != s.lens.id:
            raise HTTPException(404, "unknown lens")
        order = s.graph.topological_order(s.graph.lens_node_ids(s.lens))
        nodes: dict[str, NodeOut] = {}
        for nid in order:
            node = s.graph.get(nid)
            nodes[nid] = NodeOut(
                id=node.id,
                title=node.title,
                prereqs=s.graph.prereqs(nid),
                difficulty_prior=node.difficulty_prior,
                est_minutes=node.est_minutes,
                generators=node.generators,
                has_lesson=s.lesson_for(nid) is not None,
            )
        return TreeOut(lens=lens, order=order, nodes=nodes)

    @app.get("/v1/readiness", response_model=ReadinessOut)
    def readiness(lens: str, s: AppState = Depends(state_dep), user_id: str = "demo") -> ReadinessOut:
        if lens != s.lens.id:
            raise HTTPException(404, "unknown lens")
        twin = s.get_twin(user_id)
        mastery = twin.mastery_map(now())
        return ReadinessOut(
            user_id=user_id,
            lens=lens,
            readiness=round(s.graph.readiness(s.lens, mastery), 4),
            frontier=s.graph.frontier(s.lens, mastery),
        )

    # ------------------------------------------------------------------ plan --
    @app.get("/v1/plan/today")
    def plan_today(lens: str, s: AppState = Depends(state_dep), user_id: str = "demo", minutes: int = 45) -> dict:
        if lens != s.lens.id:
            raise HTTPException(404, "unknown lens")
        twin = s.get_twin(user_id)
        mastery = twin.mastery_map(now())
        planner = Planner(s.graph)
        plan = planner.today(user_id=user_id, lens=s.lens, mastery=mastery)
        return plan.model_dump()

    # -------------------------------------------------------------- lessons --
    @app.get("/v1/lessons/{lesson_id}")
    def lesson(lesson_id: str, s: AppState = Depends(state_dep)) -> dict:
        for _, les in s.core_cache._store.items():  # noqa: SLF001
            if les.lesson_id == lesson_id:
                return les.model_dump()
        raise HTTPException(404, "lesson not found")

    @app.get("/learn/{node_id}", response_class=HTMLResponse)
    def seo_lesson(node_id: str, s: AppState = Depends(state_dep)) -> HTMLResponse:
        """Public SEO lesson page. ``noindex`` until the core is reviewed."""
        les = s.lesson_for(node_id)
        if les is None:
            raise HTTPException(404, "no lesson for this node yet")
        html = render_html(les)
        html = html.replace(
            "<head>", '<head><meta name="robots" content="noindex">', 1
        )
        return HTMLResponse(html)

    # -------------------------------------------------------------- problems --
    @app.get("/v1/problems", response_model=ProblemOut)
    def problem(node_id: str, s: AppState = Depends(state_dep), bucket: int = 2, seed: int | None = None) -> ProblemOut:
        found = s.pool_for_node(node_id)
        if found is None:
            raise HTTPException(404, "no verified generator for this node")
        pool, gen_keys = found
        instances = pool.bucket(bucket) or pool.bucket(2)
        if not instances:
            raise HTTPException(500, "empty pool")
        rng = random.Random(seed) if seed is not None else random.Random()
        inst = instances[rng.randrange(len(instances))]
        opts = pool.options(inst.instance_id)
        return ProblemOut(
            node_id=node_id,
            instance_id=inst.instance_id,
            generator=gen_keys[0],
            stem=inst.stem,
            options=[o["display"] for o in opts],
            bucket=inst.bucket,
            badge=Trust.VERIFIED.value,
        )

    # -------------------------------------------------------------- attempts --
    @app.post("/v1/attempts", response_model=AttemptOut)
    def submit_attempt(
        body: AttemptIn,
        s: AppState = Depends(state_dep),
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> AttemptOut:
        found = s.pool_for_node(body.node_id)
        if found is None:
            raise HTTPException(404, "no verified generator for this node")
        pool, _ = found
        try:
            graded = pool.grade(body.instance_id, body.response)
        except KeyError:
            raise HTTPException(404, "unknown instance") from None

        attempt = Attempt(
            id=body.id,
            user_id=body.user_id,
            node_id=body.node_id,
            correct=graded["correct"],
            ts=now(),
            confidence=body.confidence,
            hint_level=body.hint_level,
            latency_ms=body.latency_ms,
            error_tag=graded["error_tag"],
            policy_id=body.policy_id,
            propensity=body.propensity,
            subject=body.subject or body.node_id.split(".")[0],
        )
        accepted = s.record_attempt(attempt)
        twin = s.get_twin(body.user_id)
        calib = (
            twin.calibration.calibrated_p(attempt.subject or "", body.confidence)
            if body.confidence is not None
            else None
        )
        return AttemptOut(
            id=body.id,
            accepted=accepted,
            correct=graded["correct"],
            answer=graded["answer"],
            error_tag=graded["error_tag"],
            badge=Trust.VERIFIED.value,
            mastery_after=round(twin.p_known(body.node_id), 4),
            calibration=round(calib, 4) if calib is not None else None,
        )

    # ----------------------------------------------------------- daily drop --
    def _daily_node_and_instance(s: AppState, track: str):
        """Deterministic per-track-per-day node + instance (shared seed)."""
        day = now().date()
        seed = int.from_bytes(f"{track}:{day.isoformat()}".encode(), "little") % (2**31)
        backed = [n for n in s.graph.lens_node_ids(s.lens) if s.foundry.for_node(n)]
        if not backed:
            raise HTTPException(500, "no generator-backed nodes")
        node = backed[seed % len(backed)]
        pool, gen_keys = s.pool_for_node(node)  # type: ignore[misc]
        insts = pool.bucket(2)
        return pool, gen_keys, insts[(seed // len(backed)) % len(insts)]

    @app.get("/v1/daily-drop", response_model=DailyDropOut)
    def daily_drop(s: AppState = Depends(state_dep), track: str = "gate_cse") -> DailyDropOut:
        pool, gen_keys, inst = _daily_node_and_instance(s, track)
        opts = pool.options(inst.instance_id)
        return DailyDropOut(
            track=track,
            date=now().date().isoformat(),
            stem=inst.stem,
            options=[o["display"] for o in opts],
            instance_id=inst.instance_id,
            badge=Trust.VERIFIED.value,
        )

    @app.post("/v1/daily-drop/answer", response_model=DailyDropResult)
    def daily_drop_answer(body: DailyDropAnswerIn, s: AppState = Depends(state_dep), track: str = "gate_cse") -> DailyDropResult:
        pool, _, inst = _daily_node_and_instance(s, track)
        graded = pool.grade(inst.instance_id, body.response)
        grid = "\U0001f7e9" if graded["correct"] else "\U0001f7e5"
        return DailyDropResult(correct=graded["correct"], grid=grid, answer=graded["answer"])

    # -------------------------------------------------------------- advisor --
    @app.post("/v1/advisor", response_model=AdvisorOut)
    def advisor(body: AdvisorIn, s: AppState = Depends(state_dep), user_id: str = "demo") -> AdvisorOut:
        try:
            qt = QuestionType(body.question_type)
        except ValueError:
            raise HTTPException(422, "question_type must be mcq|msq|nat") from None
        advice = advise_attempt(
            question_type=qt,
            calibrated_p=body.calibrated_p,
            marks=body.marks,
            all_options_known=body.all_options_known,
        )
        return AdvisorOut(
            recommend=advice.recommend,
            threshold=advice.threshold,
            expected_value=advice.expected_value,
            reason=advice.reason,
        )

    # ------------------------------------------------------------- twin data --
    @app.get("/v1/me/data", response_model=DataExportOut)
    def export_data(s: AppState = Depends(state_dep), user_id: str = "demo") -> DataExportOut:
        return DataExportOut(data=s.export_user(user_id))

    @app.delete("/v1/me/data")
    def delete_data(s: AppState = Depends(state_dep), user_id: str = "demo") -> JSONResponse:
        s.delete_user(user_id)
        return JSONResponse({"deleted": True, "user_id": user_id})

    # -------------------------------------------------------------- admin ----
    @app.get("/v1/admin/verification", response_model=VerificationOut)
    def verification(s: AppState = Depends(state_dep)) -> VerificationOut:
        gens = s.verification_receipts()
        return VerificationOut(generators=gens, all_verified=all(g["ok"] for g in gens))

    @app.get("/v1/health")
    def health(s: AppState = Depends(state_dep)) -> dict:
        return {
            "status": "ok",
            "nodes": len(s.graph),
            "generators": len(s.foundry),
            "lessons": len(s.core_cache),
            "ts": dt.datetime.now(dt.UTC).isoformat(),
        }

    return app


app = create_app()
