"""EdGen CLI: ``edgen serve`` and ``edgen verify``."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "edgen.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from edgen.foundry.generators.catalog import verification_reports

    reports = verification_reports(seeds=args.seeds)
    ok = True
    for r in reports:
        status = "OK" if r.ok else "FAIL"
        print(
            f"[{status}] {r.generator_id}@{r.version} "
            f"seeds={r.seeds_checked} agree={r.agreements} "
            f"disagreements={len(r.disagreements)} properties={len(r.property_failures)} "
            f"golden={len(r.golden_failures)}"
        )
        ok = ok and r.ok
    if args.json:
        print(json.dumps([r.model_dump() for r in reports], indent=2))
    return 0 if ok else 1


def cmd_plan(args: argparse.Namespace) -> int:
    from edgen.content.loader import load_gate_cse_lens
    from edgen.planner.planner import Planner
    from edgen.store.state import AppState, now

    s = AppState(pool_per_bucket=1)
    twin = s.get_twin(args.user)
    plan = Planner(s.graph).today(
        user_id=args.user, lens=load_gate_cse_lens(), mastery=twin.mastery_map(now())
    )
    print(f"Today for {args.user} ({plan.lens_id}): readiness {plan.readiness_before:.1%}")
    for item in plan.items:
        print(f"  - [{item.reason.value:8}] {item.minutes:2}m  {item.node_id}  ({item.title})")
    print(f"  expected readiness after: {plan.expected_readiness_after:.1%}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edgen", description="EdGen CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the API")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_verify = sub.add_parser("verify", help="verify all Foundry generators")
    p_verify.add_argument("--seeds", type=int, default=2000)
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    p_plan = sub.add_parser("plan", help="print today's plan for a user")
    p_plan.add_argument("--user", default="demo")
    p_plan.set_defaults(func=cmd_plan)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
