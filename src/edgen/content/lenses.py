"""Lens definitions.

A track is a lens over the shared Concept Graph. GATE CSE weights approximate
historical marks per topic (SystemsDesign §2: "GATE weights come from historical
marks per topic"). They are the *exam* lens; role lenses (Full Stack, AI, ML) land
in later waves.
"""

from __future__ import annotations

import datetime as dt

from edgen.graph.model import GoalType, Lens, LensNode

#: Topic prefix -> exam weight (marks proxy, higher = more marks per year).
#: Sums are normalised by the readiness formula, so only ratios matter.
_GATE_WEIGHTS: dict[str, float] = {
    "cs.dbms": 6.0,
    "cs.os": 6.0,
    # Later-wave GATE topics (present in the graph but weighted when authored):
    "math": 7.0,
    "cs.ds": 6.0,
    "cs.algorithms": 6.0,
    "cs.toc": 5.0,
    "cs.compiler": 4.0,
    "cs.cn": 5.0,
    "cs.coa": 5.0,
    "cs.digital": 4.0,
    "aptitude": 5.0,
}


def _topic_of(node_id: str) -> str:
    """Top-level topic key: the first two dotted parts for ``cs.*``, else the first."""
    parts = node_id.split(".")
    if parts[0] == "cs" and len(parts) >= 2:
        return ".".join(parts[:2])
    return parts[0]


def gate_cse_lens(graph_node_ids: list[str], *, exam_date: dt.date | None = None) -> Lens:
    """Build the GATE CSE exam lens over the nodes present in the graph.

    Weight of a node = the weight of its top-level topic, so a topic's total pull
    grows with the number of nodes it contributes (a rough marks proxy for W0).
    """
    nodes: list[LensNode] = []
    for i, nid in enumerate(graph_node_ids):
        topic = _topic_of(nid)
        w = _GATE_WEIGHTS.get(topic, 3.0)
        nodes.append(LensNode(lens_id="gate_cse", node_id=nid, weight=w, ord=i))
    return Lens(
        id="gate_cse",
        title="GATE CSE",
        goal_type=GoalType.EXAM,
        nodes=nodes,
        milestones=["cs.os.scheduling", "cs.dbms.transactions.conflict"],
        mock_config={"duration_min": 180, "total_marks": 100, "ga_marks": 15, "math_marks": 13},
        exam_date=exam_date,
    )
