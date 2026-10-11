"""Foundry trust properties: dual-solver agreement, determinism, grading, pools."""

from __future__ import annotations

import pytest

from edgen.foundry.generators.catalog import (
    GENERATOR_CLASSES,
    verification_reports,
)
from edgen.foundry.pool import InstancePool, PoolConfig
from edgen.foundry.verify import GeneratorVerifier, require_verified


@pytest.mark.parametrize("cls", GENERATOR_CLASSES, ids=[c.__name__ for c in GENERATOR_CLASSES])
def test_every_generator_passes_dual_solver_verification(cls):
    """The core trust claim: two independent solvers agree across seeds."""
    gen = cls()
    report = GeneratorVerifier(seeds=500).verify(gen)
    assert report.ok, (report.disagreements, report.property_failures)
    assert report.agreements == report.seeds_checked


@pytest.mark.parametrize("cls", GENERATOR_CLASSES, ids=[c.__name__ for c in GENERATOR_CLASSES])
def test_generators_are_deterministic(cls):
    gen = cls()
    for seed in range(25):
        a = gen.instance(seed)
        b = gen.instance(seed)
        assert a.params == b.params
        assert a.instance_id == b.instance_id


@pytest.mark.parametrize("cls", GENERATOR_CLASSES, ids=[c.__name__ for c in GENERATOR_CLASSES])
def test_distractors_never_equal_the_answer(cls):
    gen = cls()
    for seed in range(50):
        inst, answer, distractors = gen.solve(seed)
        for d in distractors:
            assert d.value != answer.value, f"{gen.id} seed {seed} distractor == answer"
            assert d.error_tag  # every distractor is tagged for diagnosis


def test_require_verified_returns_badge():
    gen = GENERATOR_CLASSES[0]()
    badge = require_verified(gen, seeds=200)
    assert badge.tier.value == "VERIFIED"
    assert badge.receipt.detail["dual_solver"] is True


def test_catalog_is_fully_verified():
    reports = verification_reports(seeds=300)
    assert all(r.ok for r in reports)
    assert len(reports) == len(GENERATOR_CLASSES)


def test_pool_grades_correct_and_tags_wrong():
    gen = GENERATOR_CLASSES[0]()
    pool = InstancePool(gen, PoolConfig(per_bucket=3, buckets=(2,)))
    inst = pool.bucket(2)[0]
    answer, distractors = pool.answer_key(inst.instance_id)
    ok = pool.grade(inst.instance_id, answer.comparable)
    assert ok["correct"] is True and ok["error_tag"] is None
    if distractors:
        bad = pool.grade(inst.instance_id, distractors[0].value)
        assert bad["correct"] is False
        assert bad["error_tag"] == distractors[0].error_tag


def test_pool_options_hide_the_correct_flag():
    gen = GENERATOR_CLASSES[0]()
    pool = InstancePool(gen, PoolConfig(per_bucket=2, buckets=(2,)))
    inst = pool.bucket(2)[0]
    options = pool.options(inst.instance_id)
    assert sum(1 for o in options if o["correct"]) == 1


def test_pool_instances_are_disjoint_across_buckets():
    gen = GENERATOR_CLASSES[0]()
    pool = InstancePool(gen, PoolConfig(per_bucket=2, buckets=(1, 2)))
    ids = {i.instance_id for b in (1, 2) for i in pool.bucket(b)}
    assert len(ids) == 4


def test_verifier_catches_a_broken_solver():
    """A deliberately wrong second solver must be flagged, not silently trusted."""
    gen = GENERATOR_CLASSES[0]()

    def broken(params):
        return gen.solvers[0](params).model_copy(update={"value": "WRONG", "comparable": "WRONG"})

    # Monkeypatch the second solver via a subclass instance.
    class Broken(type(gen)):  # type: ignore[misc, valid-type]
        @property
        def solvers(self):
            return (gen.solvers[0], broken)

    report = GeneratorVerifier(seeds=20).verify(Broken())
    assert not report.ok
    assert report.disagreements


def test_verifier_catches_non_determinism():
    gen = GENERATOR_CLASSES[0]()
    calls = {"n": 0}

    class Flaky(type(gen)):  # type: ignore[misc, valid-type]
        def instance(self, seed):
            calls["n"] += 1
            inst = gen.instance(seed)
            return inst.model_copy(update={"params": {**inst.params, "jitter": calls["n"]}})

    report = GeneratorVerifier(seeds=5).verify(Flaky())
    assert not report.determinism_ok
