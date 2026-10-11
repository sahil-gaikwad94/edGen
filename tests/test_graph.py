"""Graph engine: versions, aliases, readiness, frontier, track-switch credit."""

from __future__ import annotations

import datetime as dt

import pytest

from edgen.graph.authoring import GraphValidator
from edgen.graph.engine import ConceptGraph, GraphError
from edgen.graph.model import (
    ConceptNode,
    GoalType,
    GraphVersion,
    Lens,
    LensNode,
)


def _version(nodes, aliases=None) -> GraphVersion:
    return GraphVersion(
        version=1,
        created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        nodes={n.id: n for n in nodes},
        aliases=aliases or {},
    )


def _node(nid, prereqs=(), **kw):
    return ConceptNode(id=nid, title=nid, prereqs=list(prereqs), **kw)


def test_unknown_prereq_rejected():
    with pytest.raises(GraphError):
        ConceptGraph(_version([_node("a.b", ["a.missing"])]))


def test_topological_order_respects_prereqs():
    g = ConceptGraph(_version([_node("a.c", ["a.b"]), _node("a.b", ["a.a"]), _node("a.a")]))
    order = g.topological_order()
    assert order.index("a.a") < order.index("a.b") < order.index("a.c")


def test_cycle_detected():
    g = ConceptGraph(_version([_node("a.b", ["a.c"]), _node("a.c", ["a.b"])]))
    with pytest.raises(GraphError):
        g.topological_order()


def test_alias_resolution_survives_merge():
    version = _version([_node("a.new")], aliases={"a.old": "a.new"})
    g = ConceptGraph(version)
    assert g.resolve("a.old") == "a.new"
    assert g.get("a.old").id == "a.new"


def test_readiness_is_weighted_average():
    g = ConceptGraph(_version([_node("a.x"), _node("a.y")]))
    lens = Lens(
        id="L",
        title="L",
        goal_type=GoalType.MASTERY,
        nodes=[LensNode(lens_id="L", node_id="a.x", weight=3), LensNode(lens_id="L", node_id="a.y", weight=1)],
    )
    # 3*0.5 + 1*1.0 over total weight 4 = 0.625
    assert g.readiness(lens, {"a.x": 0.5, "a.y": 1.0}) == pytest.approx(0.625)


def test_readiness_zero_weight_lens():
    g = ConceptGraph(_version([_node("a.x")]))
    lens = Lens(id="L", title="L", goal_type=GoalType.MASTERY, nodes=[])
    assert g.readiness(lens, {}) == 0.0


def test_frontier_requires_prereqs_met():
    g = ConceptGraph(_version([_node("a.a"), _node("a.b", ["a.a"]), _node("a.c", ["a.b"])]))
    lens = Lens(
        id="L", title="L", goal_type=GoalType.MASTERY,
        nodes=[LensNode(lens_id="L", node_id=n) for n in ("a.a", "a.b", "a.c")],
    )
    # a.a mastered enough, a.b in the frontier band, a.c blocked by a.b.
    mastery = {"a.a": 0.8, "a.b": 0.4, "a.c": 0.4}
    frontier = g.frontier(lens, mastery)
    assert "a.b" in frontier
    assert "a.c" not in frontier  # prereq a.b (0.4) below threshold


def test_starters_include_cold_start():
    g = ConceptGraph(_version([_node("a.a"), _node("a.b", ["a.a"])]))
    lens = Lens(
        id="L", title="L", goal_type=GoalType.MASTERY,
        nodes=[LensNode(lens_id="L", node_id=n) for n in ("a.a", "a.b")],
    )
    # Brand-new learner: only a.a has prereqs met.
    starters = g.starters(lens, {})
    assert starters == ["a.a"]


def test_track_switch_preserves_shared_mastery():
    g = ConceptGraph(_version([_node("a.x"), _node("a.y"), _node("a.z")]))
    l1 = Lens(id="L1", title="L1", goal_type=GoalType.MASTERY,
              nodes=[LensNode(lens_id="L1", node_id=n) for n in ("a.x", "a.y")])
    l2 = Lens(id="L2", title="L2", goal_type=GoalType.MASTERY,
              nodes=[LensNode(lens_id="L2", node_id=n) for n in ("a.y", "a.z")])
    mastery = {"a.x": 1.0, "a.y": 1.0}
    credit = g.track_switch_credit(l1, l2, mastery)
    assert credit["from_readiness"] == pytest.approx(1.0)
    assert credit["to_readiness"] == pytest.approx(0.5)  # a.z unknown
    assert credit["shared_nodes"] == 1.0


def test_validator_flags_orphan_and_missing_coverage():
    version = _version([_node("a.solo"), _node("a.linked"), _node("a.child", ["a.linked"])])
    report = GraphValidator(version).validate(expected_topics=["a.absent"])
    assert "a.solo" in report.orphans
    assert "a.absent" in report.missing_coverage
    assert not report.ok


def test_validator_passes_real_graph(graph):
    report = GraphValidator(graph._version).validate()  # noqa: SLF001
    assert report.ok, report.messages


def test_real_graph_has_no_generator_dangling_refs(graph):
    """Every node referencing a generator must name one that exists in the catalog."""
    from edgen.foundry.generators.catalog import GENERATOR_CLASSES

    known = {f"{c().id}@{c().version}" for c in GENERATOR_CLASSES}
    for node in graph.nodes():
        for g in node.generators:
            assert g in known, f"{node.id} references unknown generator {g}"


def test_real_graph_nodes_are_cs_or_root(graph):
    for node in graph.nodes():
        assert node.id.split(".")[0] in {"cs"}, node.id
