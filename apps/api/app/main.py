"""FastAPI application — EdGen API (modular monolith, architecture §1).

API surface v1 (subset of architecture §19). All mutations accept
`Idempotency-Key`. User scope via `X-User-Id` (dev session; Google + OTP lands
in W1 weeks 1–2).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .content import ContentService, get_content
from .db import connect, init_db
from .model_gateway import cost_report
from .services import judge_svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    content = get_content()
    conn = init_db()
    try:
        created = judge_svc.ensure_pool(conn)  # pre-generate pools (serve ≤300ms)
    finally:
        # Request handlers always receive their own connection via deps.get_conn.
        # Keep no SQLite handle across the lifespan/threadpool boundary.
        conn.close()
    app.state.content = content
    app.state.pool_created = created
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="EdGen API",
        version="0.1.0",
        description="Verified-practice learning platform — W0/W1 API",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import router
    app.include_router(router, prefix="/v1")
    return app


app = create_app()
