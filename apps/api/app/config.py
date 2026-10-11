"""EdGen API configuration (env-overridable)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

REPO_ROOT = Path(os.environ.get("EDGEN_ROOT", Path(__file__).resolve().parents[3]))
CONTENT_DIR = Path(os.environ.get("EDGEN_CONTENT", REPO_ROOT / "content"))
DATA_DIR = Path(os.environ.get("EDGEN_DATA", REPO_ROOT / "data"))
DB_PATH = Path(os.environ.get("EDGEN_DB", DATA_DIR / "edgen.db"))

# HMAC key for verdict signing (ADR 5). Dev default; inject in prod.
VERDICT_SECRET = os.environ.get("EDGEN_VERDICT_SECRET", "dev-secret-do-not-use-in-prod")

# Instance pool sizing (SystemsDesign §6: pre-generated pools, serve ≤300ms)
POOL_BUCKETS = 5
POOL_INSTANCES_PER_BUCKET = 60

# Model gateway budgets (cost control §21) — W0 has no live models; budgets
# still apply so metering/cassettes are exercised from day one.
MODEL_DAILY_BUDGET_USD = float(os.environ.get("EDGEN_MODEL_BUDGET", "20.0"))
