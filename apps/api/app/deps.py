"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated, Any, Iterator

from fastapi import Depends, Header, HTTPException, Request

from .db import connect


def get_conn() -> Iterator[Any]:
    """One short-lived SQLite connection per request (thread-safe, WAL)."""
    conn = connect()
    try:
        yield conn
    finally:
        try:
            conn.commit()
        finally:
            conn.close()


def get_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id (POST /v1/session first)")
    return x_user_id


def idempotency_key(request: Request) -> str | None:
    return request.headers.get("Idempotency-Key")


ConnDep = Annotated[Any, Depends(get_conn)]
UserDep = Annotated[str, Depends(get_user_id)]
