#!/usr/bin/env python3
"""Foundry trust pipeline runner (architecture §10 publish gate).

Usage: python scripts/verify_foundry.py [--seeds 10000]
Exits non-zero if any published generator fails differential/property/golden checks.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# src-layout paths (works without editable installs)
for pkg in sorted((ROOT / "packages").glob("*/src")):
    sys.path.insert(0, str(pkg))

from edgen_foundry import all_generators, run_differential  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10_000)
    ap.add_argument("--properties", type=int, default=1_500)
    args = ap.parse_args()

    failed = False
    for gen in all_generators():
        rep = run_differential(gen, seeds=args.seeds, property_seeds=args.properties)
        s = rep.summary()
        status = "PASS" if s["passed"] else "FAIL"
        print(f"{status}  {s['generator']:<24} seeds={s['seeds']:<6} disagree={s['disagreements']} "
              f"props={s['property_failures']} golden={s['golden_cases']}/{s['golden_cases'] - s['golden_failures']} ok")
        for d in rep.disagreements[:3]:
            print("   disagreement:", d)
        for p in rep.property_failures[:3]:
            print("   property failed:", p)
        for g in rep.golden_failures[:3]:
            print("   golden failed:", g)
        failed |= not s["passed"]
    print("\nRESULT:", "ALL GENERATORS VERIFIED" if failed is False else "FAILURES PRESENT")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
