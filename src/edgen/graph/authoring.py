"""Authoring pipeline checks (SystemsDesign §2).

Automated checks run before a graph version is published: acyclic, no orphans,
and coverage against an expected topic list (past papers / job corpora).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from edgen.graph.engine import ConceptGraph, GraphError
from edgen.graph.model import GraphVersion, Lens


class ValidationReport(BaseModel):
    ok: bool
    cycles: list[list[str]] = Field(default_factory=list)
    orphans: list[str] = Field(default_factory=list)
    unknown_prereqs: list[str] = Field(default_factory=list)
    missing_coverage: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise GraphError("; ".join(self.messages) or "graph validation failed")


class GraphValidator:
    """Runs the publish-time checks for a graph version."""

    def __init__(self, version: GraphVersion) -> None:
        self._version = version

    def validate(self, *, expected_topics: list[str] | None = None) -> ValidationReport:
        report = ValidationReport(ok=True)

        # Unknown prereqs (before constructing the engine, which also checks).
        known = set(self._version.nodes)
        for node in self._version.nodes.values():
            for pre in node.prereqs:
                if self._version.resolve(pre) not in known:
                    report.unknown_prereqs.append(f"{node.id} -> {pre}")

        # Cycle detection via the engine's topological sort.
        try:
            graph = ConceptGraph(self._version)
            graph.topological_order()
        except GraphError as exc:
            report.cycles.append([str(exc)])
            report.ok = False
            report.messages.append(str(exc))
            return report

        # Orphans: concept nodes with no prereqs AND no dependents.
        referenced = {self._version.resolve(p) for n in self._version.nodes.values() for p in n.prereqs}
        for node in self._version.nodes.values():
            if node.prereqs:
                continue
            if node.id not in referenced:
                report.orphans.append(node.id)

        if expected_topics:
            missing = [t for t in expected_topics if self._version.resolve(t) not in known]
            report.missing_coverage = missing

        if report.unknown_prereqs:
            report.ok = False
            report.messages.append(f"{len(report.unknown_prereqs)} unknown prerequisite(s)")
        if report.orphans:
            report.ok = False
            report.messages.append(f"{len(report.orphans)} orphan node(s)")
        if report.missing_coverage:
            report.ok = False
            report.messages.append(f"{len(report.missing_coverage)} expected topic(s) missing")
        return report

    def validate_lens(self, lens: Lens, graph: ConceptGraph) -> ValidationReport:
        report = ValidationReport(ok=True)
        for ln in lens.nodes:
            if ln.node_id not in graph:
                report.messages.append(f"lens {lens.id} references unknown node {ln.node_id!r}")
        if not lens.nodes:
            report.messages.append(f"lens {lens.id} has no nodes")
        report.ok = not report.messages
        return report
