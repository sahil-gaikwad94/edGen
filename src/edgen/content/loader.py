"""Load content artifacts into the engine (graph, lenses, lessons)."""

from __future__ import annotations

import datetime as dt

from edgen.content import graph_v0
from edgen.content.lenses import gate_cse_lens
from edgen.content.lessons import lesson_cores
from edgen.graph.engine import ConceptGraph
from edgen.graph.model import ConceptNode, GraphVersion, NodeKind
from edgen.lesson.ir import LessonIR

GRAPH_VERSION = 1
_GRAPH_CREATED = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def build_graph_v0() -> ConceptGraph:
    """Construct the immutable v0 Concept Graph (DBMS + OS)."""
    nodes: dict[str, ConceptNode] = {}
    for nid, title, prereqs, generators, minutes, difficulty in graph_v0.nodes():
        nodes[nid] = ConceptNode(
            id=nid,
            title=title,
            kind=NodeKind.CONCEPT,
            prereqs=list(prereqs),
            generators=list(generators),
            est_minutes={"intro": max(5, minutes - 4), "standard": minutes, "deep": minutes * 2},
            difficulty_prior=difficulty,
        )
    version = GraphVersion(
        version=GRAPH_VERSION,
        created_at=_GRAPH_CREATED,
        nodes=nodes,
        aliases={},
        note="W0 graph: DBMS + OS",
    )
    return ConceptGraph(version)


def graph_version() -> GraphVersion:
    return build_graph_v0()._version  # noqa: SLF001 (intentional: full version artifact)


def load_gate_cse_lens(*, exam_date: dt.date | None = None):
    graph = build_graph_v0()
    return gate_cse_lens(list(graph._nodes.keys()), exam_date=exam_date)  # noqa: SLF001


def load_lessons() -> list[LessonIR]:
    return lesson_cores()
