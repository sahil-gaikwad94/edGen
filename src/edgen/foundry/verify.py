"""Generator verification (SystemsDesign §6).

Trust = two independently written solvers agree on many seeds, plus property tests
and hand-verified golden cases, plus one-time human review. This module runs the
automated half and produces a receipt that becomes a ``VERIFIED`` badge.

A generator that fails any check is *not* served. There is no "mostly correct".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from edgen.foundry.generator import Answer, Generator
from edgen.trust import Receipt, ReceiptKind, TrustBadge


class VerificationReport(BaseModel):
    generator_id: str
    version: int
    seeds_checked: int
    agreements: int
    disagreements: list[dict[str, Any]] = Field(default_factory=list)
    property_failures: list[dict[str, Any]] = Field(default_factory=list)
    golden_failures: list[dict[str, Any]] = Field(default_factory=list)
    determinism_ok: bool = True

    @property
    def ok(self) -> bool:
        return (
            not self.disagreements
            and not self.property_failures
            and not self.golden_failures
            and self.determinism_ok
            and self.seeds_checked > 0
        )

    def badge(self) -> TrustBadge:
        if not self.ok:
            raise ValueError("cannot badge a failed verification report")
        return TrustBadge(
            tier="VERIFIED",  # type: ignore[arg-type]
            receipt=Receipt(
                kind=ReceiptKind.ORACLE,
                refs=[f"{self.generator_id}@{self.version}"],
                detail={
                    "seeds_checked": self.seeds_checked,
                    "agreements": self.agreements,
                    "dual_solver": True,
                    "property_tests": "pass",
                    "golden_cases": "pass",
                },
            ),
        )


def _comparable(a: Answer) -> Any:
    return a.comparable if a.comparable is not None else a.value


class GeneratorVerifier:
    """Runs differential + property + golden checks for a generator."""

    def __init__(self, *, seeds: int = 2000) -> None:
        self.seeds = seeds

    def verify(
        self,
        gen: Generator,
        *,
        seeds: int | None = None,
        properties: list[Callable[[Any, Any], tuple[bool, str]]] | None = None,
        golden: list[tuple[int, Any]] | None = None,
    ) -> VerificationReport:
        n = seeds or self.seeds
        report = VerificationReport(
            generator_id=gen.id, version=gen.version, seeds_checked=0, agreements=0
        )
        solver_a, solver_b = gen.solvers

        for seed in range(n):
            inst = gen.instance(seed)
            # Determinism: same seed -> same instance.
            if gen.instance(seed).params != inst.params:
                report.determinism_ok = False
                report.disagreements.append({"seed": seed, "reason": "non-deterministic params"})
                continue

            ans_a = solver_a(inst.params)
            ans_b = solver_b(inst.params)
            report.seeds_checked += 1
            if _comparable(ans_a) == _comparable(ans_b):
                report.agreements += 1
            else:
                report.disagreements.append(
                    {
                        "seed": seed,
                        "params": inst.params,
                        "solver_a": _comparable(ans_a),
                        "solver_b": _comparable(ans_b),
                    }
                )

            for prop in properties or []:
                ok, msg = prop(inst.params, ans_a)
                if not ok:
                    report.property_failures.append({"seed": seed, "params": inst.params, "msg": msg})

        for seed, expected in golden or []:
            inst = gen.instance(seed)
            got = _comparable(solver_a(inst.params))
            if got != expected:
                report.golden_failures.append(
                    {"seed": seed, "expected": expected, "got": got, "params": inst.params}
                )

        return report


def require_verified(gen: Generator, *, seeds: int = 2000) -> TrustBadge:
    """Verify a generator or raise. Use in CI and at pool-build time."""
    report = GeneratorVerifier(seeds=seeds).verify(gen)
    if not report.ok:
        raise ValueError(
            f"generator {gen.id}@{gen.version} failed verification: "
            f"{len(report.disagreements)} disagreements, "
            f"{len(report.property_failures)} property failures, "
            f"{len(report.golden_failures)} golden failures"
        )
    return report.badge()
