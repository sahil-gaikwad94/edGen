"""Application state and persistence seams.

Phase 1 ships an in-memory implementation so the whole system runs and tests with
zero external services. The interfaces (``TwinStore``, ``AttemptLog``) are the
seams where Postgres/Redis plug in — the migrations in ``/migrations`` already
define the target schema.
"""

from edgen.store.state import AppState, get_state

__all__ = ["AppState", "get_state"]
