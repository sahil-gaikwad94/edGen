"""Content layer: versioned Concept Graph, lens definitions, and lesson cores.

Content is data, not code (architecture §25: graph versions and generators are
versioned artifacts with rollback). This package loads them into the engine.
"""

from edgen.content.loader import (
    build_graph_v0,
    graph_version,
    load_gate_cse_lens,
    load_lessons,
)

__all__ = ["build_graph_v0", "load_gate_cse_lens", "load_lessons", "graph_version"]
