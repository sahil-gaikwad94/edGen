"""Published curriculum coverage and estimate consistency checks."""

import pytest
import yaml

from apps.api.app.content import ContentService

EXPECTED_TRACKS = {"gate_cse", "full_stack", "ai", "ml"}


def test_all_four_curricula_are_discoverable_with_honest_experience_status(client):
    track_response = client.get("/v1/tracks")
    syllabus_response = client.get("/v1/syllabi")
    assert track_response.status_code == syllabus_response.status_code == 200

    tracks = {track["id"]: track for track in track_response.json()["tracks"]}
    summaries = {item["track_id"]: item for item in syllabus_response.json()["syllabi"]}
    assert set(tracks) == set(summaries) == EXPECTED_TRACKS
    assert tracks["gate_cse"]["experience_status"] == "partial"
    assert all(tracks[track_id]["experience_status"] == "syllabus"
               for track_id in EXPECTED_TRACKS - {"gate_cse"})

    for track_id, summary in summaries.items():
        assert tracks[track_id]["syllabus_available"] is True
        assert summary["phase_count"] > 0
        assert summary["module_count"] > 0
        assert summary["topic_count"] > summary["module_count"]
        assert summary["estimated_hours"] > 0


def test_syllabus_details_are_complete_and_estimates_reconcile(client):
    for track_id in sorted(EXPECTED_TRACKS):
        response = client.get(f"/v1/syllabi/{track_id}")
        assert response.status_code == 200
        syllabus = response.json()
        phases = syllabus["phases"]
        modules = [module for phase in phases for module in phase["modules"]]
        module_ids = [module["id"] for module in modules]

        assert len(phases) == syllabus["phase_count"]
        assert len(modules) == syllabus["module_count"]
        assert len(module_ids) == len(set(module_ids))
        assert sum(module["hours"] for module in modules) == syllabus["estimated_hours"]
        assert sum(len(module["topics"]) for module in modules) == syllabus["topic_count"]
        assert all(module["topics"] and all(topic.strip() for topic in module["topics"])
                   for module in modules)
        assert all(module["hours"] > 0 for module in modules)

    gate = client.get("/v1/syllabi/gate_cse").json()
    assert sum(section["marks"] for section in gate["exam_structure"]["sections"]) == gate["exam_structure"]["total_marks"]


def test_loader_rejects_a_declared_total_that_differs_from_module_hours(tmp_path):
    syllabus_dir = tmp_path / "syllabi"
    syllabus_dir.mkdir()
    syllabus = {
        "track_id": "gate_cse",
        "version": 1,
        "title": "GATE CSE",
        "tagline": "Exam pathway",
        "description": "A test syllabus.",
        "goal_type": "exam",
        "audience": "Candidates",
        "outcome": "Prepare for the exam.",
        "estimated_hours": 20,
        "phases": [{
            "id": "foundations",
            "title": "Foundations",
            "summary": "Start here.",
            "modules": [{
                "id": "logic",
                "title": "Logic",
                "summary": "Reason carefully.",
                "hours": 10,
                "topics": ["Propositions", "Proofs"],
            }],
        }],
    }
    (syllabus_dir / "gate_cse.yaml").write_text(yaml.safe_dump(syllabus))
    service = ContentService.__new__(ContentService)
    service.content_dir = tmp_path
    service.tracks = {"gate_cse": {"goal_type": "exam"}}

    with pytest.raises(ValueError, match=r"estimated_hours \(20\) does not match module total \(10\)"):
        service._load_syllabi()
