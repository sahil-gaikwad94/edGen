"""Initialize the local database and prewarm published Problem Foundry pools."""
from __future__ import annotations

from .db import init_db
from .services.judge_svc import ensure_pool


def main() -> int:
    conn = init_db()
    try:
        created = ensure_pool(conn)
    finally:
        conn.close()
    total = sum(created.values())
    print(f"Database ready; created {total} instances across {len(created)} generators.")
    for generator_id, count in sorted(created.items()):
        print(f"  {generator_id:<28} +{count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
