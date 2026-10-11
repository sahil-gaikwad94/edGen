"""Graph + lens engine tests (SystemsDesign §2)."""
from pathlib import Path

import pytest

from edgen_graph import ConceptGraph, GraphValidationError, load_content

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return load_content(ROOT / "content")


def test_graph_v0_size_and_validation(bundle):
    g = bundle.graph
    assert g.version == 0
    assert len(g.nodes) >= 100  # W0 gate: ~120 nodes across OS + DBMS
    subjects = {n.subject for n in g.nodes.values()}
    assert subjects == {"os", "dbms"}
    topo = g.topo_order()  # raises on cycle
    assert len(topo) == len(g.nodes)


def test_cycle_detection():
    from edgen_graph.models import Node

    a = Node(id="a", title="a", kind="concept", topic="t", subject="s", prereqs=("b",), est_minutes=5, difficulty_prior=0.5)
    b = Node(id="b", title="b", kind="concept", topic="t", subject="s", prereqs=("a",), est_minutes=5, difficulty_prior=0.5)
    with pytest.raises(GraphValidationError, match="cycle"):
        ConceptGraph(0, [a, b])


def test_unknown_prereq_rejected():
    from edgen_graph.models import Node

    a = Node(id="a", title="a", kind="concept", topic="t", subject="s", prereqs=("ghost",), est_minutes=5, difficulty_prior=0.5)
    with pytest.raises(GraphValidationError, match="unknown prereq"):
        ConceptGraph(0, [a])


def test_readiness_weighted_mean(bundle):
    g = bundle.graph
    lens = bundle.lenses["gate_cse"]
    assert abs(g.readiness(lens, lambda _: 1.0) - 1.0) < 1e-9
    assert abs(g.readiness(lens, lambda _: 0.0) - 0.0) < 1e-9
    # priors give a middling readiness
    r = g.readiness(lens, lambda nid: g.get(nid).difficulty_prior)
    assert 0.3 < r < 0.7
    # upcoming track lens has no matching nodes → honest None
    ai = bundle.lenses["ai"]
    assert g.readiness(ai, lambda _: 0.5) is None


def test_frontier_and_remediation(bundle):
    g = bundle.graph
    priors = {nid: n.difficulty_prior for nid, n in g.nodes.items()}
    m = lambda nid: priors.get(nid, 0.5)
    frontier = g.frontier(m)
    # fresh learner: only roots (no prereqs) are unlocked
    roots = [nid for nid, n in g.nodes.items() if not n.prereqs]
    assert set(frontier) == set(roots)
    # mastery on roots opens the next layer
    m2 = dict(priors)
    for r in roots:
        m2[r] = 0.9
    frontier2 = g.frontier(m2.__getitem__)
    assert len(frontier2) > len(frontier)
    # remediation catches stuck-but-unlocked nodes
    m3 = dict(m2)
    first_child = next(iter(g.nodes[roots[0]].prereqs), None) or "os.process.threads"
    m3[first_child] = 0.1
    rem = g.remediation(m3.__getitem__)
    assert first_child in rem


def test_tracks_and_lenses_declared(bundle):
    assert set(bundle.tracks) == {"gate_cse", "full_stack", "ai", "ml"}
    assert bundle.tracks["gate_cse"]["status"] == "active"
    assert set(bundle.lenses) == set(bundle.tracks)
    lens = bundle.lenses["gate_cse"]
    assert lens.goal_type == "exam"
    assert lens.weighted_nodes and all(w > 0 for w in lens.weights.values())
