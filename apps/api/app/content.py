"""Content loading: graph, lenses, lessons, foundry registry (cache-first)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from edgen_graph import ConceptGraph, Lens, load_content
from edgen_lesson_ir import LessonCore, load_lesson, load_sources

from . import config


class ContentService:
    """Process-wide immutable content (graph versions are immutable per ADR 2)."""

    def __init__(self, content_dir: Path | None = None):
        self.content_dir = Path(content_dir or config.CONTENT_DIR)
        bundle = load_content(self.content_dir)
        self.graph: ConceptGraph = bundle.graph
        self.lenses: dict[str, Lens] = bundle.lenses
        self.tracks: dict[str, dict] = bundle.tracks
        self.syllabi: dict[str, dict[str, Any]] = self._load_syllabi()
        self.sources = load_sources(self.content_dir)
        self._lessons: dict[str, LessonCore] = {}
        self._lesson_lock = threading.Lock()
        self._registry = self._load_registry()
        self._load_all_lessons()

    def _load_registry(self) -> dict[str, Any]:
        import yaml

        path = self.content_dir / "foundry" / "registry.yaml"
        if not path.exists():
            return {"generators": []}
        data = yaml.safe_load(path.read_text())
        return {
            g["id"]: g for g in data.get("generators", [])
        }

    def _load_syllabi(self) -> dict[str, dict[str, Any]]:
        """Load and validate the curriculum maps before exposing them via API."""
        import yaml

        syllabus_dir = self.content_dir / "syllabi"
        if not syllabus_dir.exists():
            raise ValueError(f"missing syllabus directory: {syllabus_dir}")
        syllabi: dict[str, dict[str, Any]] = {}
        required_text = ("title", "tagline", "description", "audience", "outcome")

        for path in sorted(syllabus_dir.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text())
            if not isinstance(raw, dict):
                raise ValueError(f"{path.name}: syllabus must be a YAML mapping")
            track_id = raw.get("track_id")
            if not track_id or track_id not in self.tracks:
                raise ValueError(f"{path.name}: syllabus references unknown track {track_id!r}")
            if path.stem != track_id:
                raise ValueError(f"{path.name}: filename must match track id {track_id!r}")
            if track_id in syllabi:
                raise ValueError(f"duplicate syllabus for track {track_id}")
            if raw.get("goal_type") != self.tracks[track_id].get("goal_type"):
                raise ValueError(f"{path.name}: goal_type must match track registry")
            if any(not isinstance(raw.get(field), str) or not raw[field].strip() for field in required_text):
                raise ValueError(f"{path.name}: required metadata fields must be non-empty strings")
            if not isinstance(raw.get("version"), int) or isinstance(raw["version"], bool) or raw["version"] < 1:
                raise ValueError(f"{path.name}: version must be a positive integer")

            phases = raw.get("phases")
            if not isinstance(phases, list) or not phases:
                raise ValueError(f"{path.name}: syllabus needs at least one phase")
            phase_ids: set[str] = set()
            module_ids: set[str] = set()
            module_hours = 0
            for phase in phases:
                if not isinstance(phase, dict):
                    raise ValueError(f"{path.name}: phases must be mappings")
                phase_id = phase.get("id")
                if not isinstance(phase_id, str) or not phase_id.strip() or phase_id in phase_ids:
                    raise ValueError(f"{path.name}: missing/duplicate phase id")
                phase_ids.add(phase_id)
                if any(not isinstance(phase.get(field), str) or not phase[field].strip() for field in ("title", "summary")):
                    raise ValueError(f"{path.name}/{phase_id}: title and summary are required")
                modules = phase.get("modules")
                if not isinstance(modules, list) or not modules:
                    raise ValueError(f"{path.name}/{phase_id}: phase needs modules")
                for module in modules:
                    if not isinstance(module, dict):
                        raise ValueError(f"{path.name}/{phase_id}: modules must be mappings")
                    mid = module.get("id")
                    if not isinstance(mid, str) or not mid.strip() or mid in module_ids:
                        raise ValueError(f"{path.name}: missing/duplicate module id {mid!r}")
                    module_ids.add(mid)
                    if any(not isinstance(module.get(field), str) or not module[field].strip() for field in ("title", "summary")):
                        raise ValueError(f"{path.name}/{mid}: title and summary are required")
                    topics = module.get("topics")
                    if not isinstance(topics, list) or not topics or not all(isinstance(topic, str) and topic.strip() for topic in topics):
                        raise ValueError(f"{path.name}/{mid}: topics must be non-empty strings")
                    hours = module.get("hours")
                    if not isinstance(hours, int) or isinstance(hours, bool) or hours <= 0:
                        raise ValueError(f"{path.name}/{mid}: estimated hours must be a positive integer")
                    practice = module.get("practice", [])
                    if not isinstance(practice, list) or any(not isinstance(item, str) or not item.strip() for item in practice):
                        raise ValueError(f"{path.name}/{mid}: practice outcomes must be strings")
                    module_hours += hours

            declared_hours = raw.get("estimated_hours")
            if not isinstance(declared_hours, int) or isinstance(declared_hours, bool) or declared_hours <= 0:
                raise ValueError(f"{path.name}: estimated_hours must be a positive integer")
            if declared_hours != module_hours:
                raise ValueError(
                    f"{path.name}: estimated_hours ({declared_hours}) does not match module total ({module_hours})"
                )

            exam_structure = raw.get("exam_structure")
            if exam_structure is not None:
                sections = exam_structure.get("sections") if isinstance(exam_structure, dict) else None
                total_marks = exam_structure.get("total_marks") if isinstance(exam_structure, dict) else None
                if not isinstance(sections, list) or not sections:
                    raise ValueError(f"{path.name}: exam sections must be a non-empty list")
                if not isinstance(total_marks, int) or isinstance(total_marks, bool) or total_marks <= 0:
                    raise ValueError(f"{path.name}: total_marks must be a positive integer")
                if any(not isinstance(section, dict) or not isinstance(section.get("marks"), int)
                       or isinstance(section.get("marks"), bool) or section["marks"] <= 0
                       or not isinstance(section.get("title"), str) or not section["title"].strip()
                       for section in sections):
                    raise ValueError(f"{path.name}: exam sections need a title and positive integer marks")
                if sum(section["marks"] for section in sections) != total_marks:
                    raise ValueError(f"{path.name}: section marks must sum to total_marks")
            syllabi[track_id] = raw

        missing = set(self.tracks) - set(syllabi)
        if missing:
            raise ValueError("tracks missing syllabus files: " + ", ".join(sorted(missing)))
        return syllabi

    def syllabus_summary(self, track_id: str) -> dict[str, Any]:
        syllabus = self.syllabi[track_id]
        modules = [module for phase in syllabus["phases"] for module in phase["modules"]]
        return {
            "track_id": track_id,
            "title": syllabus["title"],
            "tagline": syllabus["tagline"],
            "description": syllabus["description"],
            "goal_type": syllabus["goal_type"],
            "audience": syllabus.get("audience"),
            "outcome": syllabus.get("outcome"),
            "phase_count": len(syllabus["phases"]),
            "module_count": len(modules),
            "topic_count": sum(len(module["topics"]) for module in modules),
            "estimated_hours": sum(int(module["hours"]) for module in modules),
            "experience_status": self.tracks[track_id].get("experience_status", self.tracks[track_id].get("status")),
            "syllabus_version": int(syllabus.get("version", 1)),
        }

    @property
    def published_generators(self) -> dict[str, dict]:
        return {k: v for k, v in self._registry.items() if v.get("trust", {}).get("status") == "published"}

    def _load_all_lessons(self) -> None:
        lessons_dir = self.content_dir / "lessons"
        if not lessons_dir.exists():
            return
        for f in sorted(lessons_dir.glob("*.json")):
            lesson = load_lesson(f, self.sources)
            self._lessons[lesson.node_id] = lesson

    # -- lessons ----------------------------------------------------------
    def has_authored_lesson(self, node_id: str) -> bool:
        return node_id in self._lessons

    def authored_lesson(self, node_id: str) -> LessonCore | None:
        return self._lessons.get(node_id)

    def scaffold_lesson(self, node_id: str) -> LessonCore | None:
        """Draft core assembled from graph metadata (degrade ladder: serve a
        scaffold + 'updating' badge rather than nothing). Long-tail cores are
        authored on demand (architecture §6 pre-generation note)."""
        try:
            node = self.graph.get(node_id)
        except KeyError:
            return None
        blocks: list[dict[str, Any]] = [
            {
                "id": "s1",
                "type": "claim",
                "badge": "MODEL",
                "text": f"**{node.title}** — this core is a draft scaffold built from the concept graph. "
                        f"Estimated study time: {node.est_minutes} min. The full reviewed core is queued for authoring.",
            }
        ]
        if node.prereqs:
            titles = ", ".join(self.graph.get(p).title for p in node.prereqs if p in self.graph)
            blocks.append({"id": "s2", "type": "claim", "badge": "MODEL",
                           "text": f"Before this: **{titles}**."})
        for i, m in enumerate(node.misconceptions):
            blocks.append({"id": f"m{i + 1}", "type": "counterexample", "badge": "MODEL",
                           "text": f"Misconception to avoid: {m}"})
        if node.generators:
            blocks.append({"id": "s3", "type": "check", "badge": "VERIFIED",
                           "foundry": node.generators[0],
                           "prompt": "Verified practice is available for this node — every answer is graded by code."})
        return _scaffold_core(node_id, node, blocks)


def _scaffold_core(node_id: str, node, blocks: list[dict]) -> LessonCore:
    from edgen_lesson_ir import Block

    return LessonCore(
        lesson_id=f"{node_id}@scaffold",
        node_id=node_id,
        core_version=0,
        title=node.title,
        review_status="draft",
        blocks=[Block.model_validate(b) for b in blocks],
    )


_service: ContentService | None = None
_lock = threading.Lock()


def get_content() -> ContentService:
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = ContentService()
    return _service
