"""Concept Graph and track lenses.

One immutable, versioned Concept Graph (~1.5-2k nodes at launch). A *track* is a
lens: a chosen subgraph plus weights, ordering hints, milestones and a goal type.
Tracks share nodes, so mastery carries across a track switch (SystemsDesign §2).
"""

from edgen.graph.authoring import GraphValidator, ValidationReport
from edgen.graph.engine import ConceptGraph, GraphError
from edgen.graph.model import (
    ConceptNode,
    GoalType,
    GraphVersion,
    Lens,
    LensNode,
    NodeKind,
)

__all__ = [
    "ConceptNode",
    "GraphVersion",
    "Lens",
    "LensNode",
    "NodeKind",
    "GoalType",
    "ConceptGraph",
    "GraphError",
    "GraphValidator",
    "ValidationReport",
]
