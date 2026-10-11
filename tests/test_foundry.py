"""Foundry trust pipeline: 10k-seed differential + properties + goldens (ADR 8).

The publish gate: a generator may not be served until this passes.
"""
import pytest

from edgen_foundry import all_generators, get_generator, run_differential

GEN_IDS = [g.id for g in all_generators()]

assert GEN_IDS == [
    "dbms.fd_closure",
    "dbms.serializability",
    "os.cpu_scheduling",
    "os.disk_scheduling",
    "os.page_replacement",
], f"unexpected generator roster: {GEN_IDS}"


@pytest.mark.differential
@pytest.mark.parametrize("gen_id", GEN_IDS)
def test_differential_10k_seeds(gen_id):
    gen = get_generator(gen_id)
    rep = run_differential(gen, seeds=10_000, property_seeds=1_500)
    assert not rep.disagreements, rep.disagreements[:3]
    assert not rep.property_failures, rep.property_failures[:3]
    assert rep.golden_run >= 3, "every generator needs hand-verified golden cases"
    assert not rep.golden_failures, rep.golden_failures[:3]


def test_every_generator_is_published_in_registry():
    import yaml
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    reg = yaml.safe_load((ROOT / "content/foundry/registry.yaml").read_text())
    ids = {g["id"] for g in reg["generators"]}
    assert ids == set(GEN_IDS)
    for g in reg["generators"]:
        assert g["trust"]["status"] == "published"
        assert g["trust"]["differential_seeds"] >= 10_000


def test_answer_keys_never_in_served_payload(client, user):
    """Serving a problem must not leak params or answers (server-side keys)."""
    r = client.get("/v1/problems/os.cpu_scheduling", headers=user)
    assert r.status_code == 200
    payload = r.json()
    assert set(payload) >= {"instance_id", "generator_id", "statement", "input_spec", "hints"}
    assert "params" not in payload and "answer" not in payload


def test_mistake_models_match_known_errors(client, user):
    """A wrong answer that matches a tagged mistake gets the error tag (diagnose)."""
    r = client.get("/v1/problems/os.page_replacement?bucket=3", headers=user)
    p = r.json()
    from apps.api.app.db import connect, loads
    from edgen_foundry import get_generator as gg

    conn = connect()
    params = loads(conn.execute(
        "select params from instance_pool where instance_id=?", (p["instance_id"],)).fetchone()["params"])
    conn.close()
    gen = gg("os.page_replacement")
    key = gen.solve_a(params)
    mistakes = gen.mistakes(params)
    assert mistakes, "page replacement should model at least one common mistake"
    # every mistake model must be wrong (≠ key)
    assert all(gen.canonical(m.answer) != gen.canonical(key) for m in mistakes)
    # submitting a mistake's answer tags the error
    r = client.post("/v1/attempts", json={
        "generator_id": p["generator_id"], "instance_id": p["instance_id"],
        "answer": mistakes[0].answer, "confidence": 75,
    }, headers=user)
    body = r.json()
    assert body["verdict"]["correct"] is False
    assert body["verdict"]["error_tag"] == mistakes[0].tag
    assert body["verdict"]["trust_label"] == "VERIFIED"
    assert body["verdict"]["signature"]
