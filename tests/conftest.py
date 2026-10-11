"""Test bootstrap: package paths + isolated test DB."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for pkg in sorted((ROOT / "packages").glob("*/src")):
    p = str(pkg)
    if p not in sys.path:
        sys.path.insert(0, p)

# Isolated DB per test session (config reads env at import time)
_TEST_DIR = tempfile.mkdtemp(prefix="edgen-test-")
os.environ.setdefault("EDGEN_DB", str(Path(_TEST_DIR) / "test.db"))
os.environ.setdefault("EDGEN_DATA", _TEST_DIR)
os.environ.setdefault("EDGEN_ROOT", str(ROOT))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from apps.api.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user(client):
    r = client.post("/v1/session", json={})
    assert r.status_code == 200
    return {"X-User-Id": r.json()["user_id"]}
