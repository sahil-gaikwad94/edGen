"""The W0 generator catalog: 5 verified GATE generators (DBMS + OS).

Each generator is verified (dual-solver agreement + property checks + golden
cases) before it is allowed into the registry. ``load_generators`` returns a
Foundry with only verified generators; ``verification_reports`` exposes the
receipts for the admin/review plane.
"""

from __future__ import annotations

from edgen.foundry.generator import BaseGenerator
from edgen.foundry.generators.bankers import BankersAlgorithmGenerator
from edgen.foundry.generators.bplus_height import BPlusTreeHeightGenerator
from edgen.foundry.generators.cache_mapping import CacheMappingGenerator
from edgen.foundry.generators.fd_closure import FDClosureGenerator
from edgen.foundry.generators.page_replacement import FIFOPageReplacementGenerator
from edgen.foundry.registry import Foundry
from edgen.foundry.verify import GeneratorVerifier, VerificationReport

GENERATOR_CLASSES: list[type[BaseGenerator]] = [
    FDClosureGenerator,
    CacheMappingGenerator,
    BankersAlgorithmGenerator,
    FIFOPageReplacementGenerator,
    BPlusTreeHeightGenerator,
]

#: Seeds used for the CI verification sweep. W0 uses 2k; CI can raise this.
VERIFY_SEEDS = 2000


def _properties(gen: BaseGenerator):
    """Generator-specific invariant checks: (params, answer) -> (ok, message)."""
    props = []

    if gen.id == "fd_closure":
        def closure_superset(params, answer):
            ok = set(params["start"]) <= set(answer.value)
            return ok, "closure must contain the start attributes"

        def closure_within_schema(params, answer):
            ok = set(answer.value) <= set(params["attrs"])
            return ok, "closure must be a subset of the schema attributes"

        props += [closure_superset, closure_within_schema]

    if gen.id == "cache_mapping":
        def index_in_range(params, answer):
            ok = 0 <= answer.value < params["num_lines"]
            return ok, "set index must be in [0, num_lines)"

        props.append(index_in_range)

    if gen.id == "page_replacement_fifo":
        def faults_bounds(params, answer):
            lo = len(set(params["ref"]))
            hi = len(params["ref"])
            ok = lo <= answer.value <= hi
            return ok, "faults must be between distinct pages and total references"

        props.append(faults_bounds)

    if gen.id == "bplus_height":
        def height_nonneg(params, answer):
            return answer.value >= 0, "height must be non-negative"

        props.append(height_nonneg)

    return props


def _golden(gen: BaseGenerator) -> list[tuple[int, object]]:
    """Hand-verified golden cases, keyed by the generator's own seed space.

    These are the "one-time human review" leg of the trust chain: a human checked
    that the verified solver output is also the pedagogically correct answer.
    """
    table: dict[str, list[tuple[int, object]]] = {
        # seed -> verified expected value (computed and hand-checked).
        "fd_closure": [(0, "ABCD"), (2, "AC")],
        "cache_mapping": [(0, 1), (2, 1)],
        "bankers_safe": [(0, True), (1, False)],
        "page_replacement_fifo": [(0, 3), (2, 8)],
        "bplus_height": [(0, 13), (2, 4)],
    }
    return table.get(gen.id, [])


def verification_reports(seeds: int = VERIFY_SEEDS) -> list[VerificationReport]:
    verifier = GeneratorVerifier(seeds=seeds)
    return [
        verifier.verify(g, properties=_properties(g), golden=_golden(g))
        for g in (c() for c in GENERATOR_CLASSES)
    ]


def load_generators(*, seeds: int = VERIFY_SEEDS) -> Foundry:
    """Build the catalog, registering only generators that pass verification."""
    foundry = Foundry()
    verifier = GeneratorVerifier(seeds=seeds)
    for cls in GENERATOR_CLASSES:
        gen = cls()
        report = verifier.verify(gen, properties=_properties(gen), golden=_golden(gen))
        if not report.ok:
            raise ValueError(
                f"generator {gen.id}@{gen.version} failed verification: "
                f"{len(report.disagreements)} disagreements, "
                f"{len(report.property_failures)} property failures, "
                f"{len(report.golden_failures)} golden failures"
            )
        foundry.register(gen)
    return foundry
