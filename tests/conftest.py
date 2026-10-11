"""Shared fixtures."""

from __future__ import annotations

import datetime as dt

import pytest

from edgen.content.loader import build_graph_v0, load_gate_cse_lens
from edgen.store.state import AppState


@pytest.fixture(scope="session")
def graph():
    return build_graph_v0()


@pytest.fixture(scope="session")
def lens():
    return load_gate_cse_lens()


@pytest.fixture()
def state():
    # Small pools + fewer seeds keep tests fast; the maths is seed-independent.
    return AppState(pool_per_bucket=4, verify_seeds=200)


@pytest.fixture()
def utc():
    def _make(y=2026, m=1, d=1, h=0):
        return dt.datetime(y, m, d, h, tzinfo=dt.UTC)

    return _make
