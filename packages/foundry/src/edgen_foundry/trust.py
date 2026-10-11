"""Foundry trust pipeline (SystemsDesign §6 / architecture §10).

Publish pipeline: static checks → A == B on 10k+ seeds → property tests →
hand-verified golden cases → (human review recorded in registry) → publish vN.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .protocol import Generator


@dataclass
class TrustReport:
    generator_id: str
    seeds_run: int = 0
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    property_failures: list[dict[str, Any]] = field(default_factory=list)
    golden_failures: list[dict[str, Any]] = field(default_factory=list)
    golden_run: int = 0
    created_at: str = ""

    @property
    def passed(self) -> bool:
        return not self.disagreements and not self.property_failures and not self.golden_failures and self.golden_run > 0

    def summary(self) -> dict[str, Any]:
        return {
            "generator": self.generator_id,
            "seeds": self.seeds_run,
            "disagreements": len(self.disagreements),
            "property_failures": len(self.property_failures),
            "golden_cases": self.golden_run,
            "golden_failures": len(self.golden_failures),
            "passed": self.passed,
        }


def _bucket(i: int) -> int:
    return 1 + (i % 5)


def run_differential(
    gen: Generator,
    *,
    seeds: int = 10_000,
    seed0: int = 0,
    property_seeds: int | None = None,
    golden_path: Path | None = None,
    max_record: int = 5,
) -> TrustReport:
    """Two independent solvers must agree; properties must hold; goldens must match."""
    rep = TrustReport(generator_id=gen.id, created_at=datetime.now(timezone.utc).isoformat())

    for i in range(seeds):
        rng = random.Random(seed0 + i * 7919)
        params = gen.sample(rng, _bucket(i))
        a = gen.solve_a(params)
        b = gen.solve_b(params)
        rep.seeds_run += 1
        if not gen.agree(params, a, b):
            if len(rep.disagreements) < max_record:
                rep.disagreements.append(
                    {"seed": seed0 + i, "params": _trim(params), "a": repr(a), "b": repr(b)}
                )
            continue
        # properties run on the verified answer (cheaper: subset of seeds)
        if i % max(1, seeds // max(1, property_seeds or seeds // 10)) == 0:
            key = a
            for name, ok in gen.properties(params, key):
                if not ok and len(rep.property_failures) < max_record:
                    rep.property_failures.append({"seed": seed0 + i, "property": name, "params": _trim(params)})

    if golden_path is None:
        golden_path = _default_golden_path(gen.id)
    if golden_path and Path(golden_path).exists():
        cases = yaml.safe_load(Path(golden_path).read_text()).get("cases", [])
        for case in cases:
            rep.golden_run += 1
            params = case["params"]
            if "expected" in case:
                got = gen.answer_key(params, gen.solve_a(params))
                if got != str(case["expected"]):
                    rep.golden_failures.append(
                        {"case": case.get("name"), "expected": case["expected"], "got": got}
                    )
            elif "expect_check" in case:
                if not gen.check(params, case["expect_check"]):
                    rep.golden_failures.append(
                        {"case": case.get("name"), "expected": case["expect_check"], "got": "check() rejected"}
                    )
            else:
                rep.golden_failures.append({"case": case.get("name"), "error": "no expected/expect_check"})
    return rep


def _default_golden_path(gen_id: str) -> Path | None:
    # content/foundry/golden/{gen_id}.yaml relative to repo root
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "content" / "foundry" / "golden" / f"{gen_id}.yaml"
        if cand.exists():
            return cand
    return None


def _trim(params: dict[str, Any], limit: int = 400) -> dict[str, Any]:
    out = repr(params)
    return {"params": out[:limit] + ("…" if len(out) > limit else "")}
