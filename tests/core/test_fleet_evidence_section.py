"""Tests for D4C Evidence Pack v2 fleet section builder."""

import time

from uar.core.fleet_evidence_section import build_fleet_evidence_section


def test_fleet_evidence_section_nominal_when_no_signals():
    section = build_fleet_evidence_section([], generated_at=123.0)

    assert section["section"] == "fleet_signal_evidence"
    assert section["generated_at"] == 123.0
    assert section["summary"]["status"] == "nominal"
    assert "Fleet status: **nominal**" in section["markdown"]
    assert "No fleet signals were detected" in section["markdown"]


def test_fleet_evidence_section_includes_fleet_signal_and_replay_linkage():
    records = [
        {
            "run_id": "run-1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-a"},
            "created_at": 100.0,
        }
    ]

    section = build_fleet_evidence_section(records, generated_at=456.0)

    top = section["summary"]["top_signal"]
    assert top["linkage"]["replay"] == {"run_id": "run-1", "available": True}
    assert "Fleet status: **critical**" in section["markdown"]
    assert "Service signal: svc-a" in section["markdown"]
    assert "Latest replay run: `run-1`" in section["markdown"]
    assert "Evidence refs: `run:run-1`" in section["markdown"]


def test_fleet_evidence_section_includes_linked_outcomes_and_trust():
    now = time.time()
    records = [
        {
            "run_id": "run-2",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {
                "service": "svc-b",
                "incident_id": "inc-1",
                "recommendation_id": "rec-1",
            },
            "created_at": now,
        }
    ]
    outcomes = [
        {
            "recommendation_id": "rec-1",
            "outcome_type": "resolved",
            "recorded_at": now,
        }
        for _ in range(5)
    ]
    metadata = [
        {
            "recommendation_id": "rec-1",
            "category": "fleet_recovery",
            "source": "fleet_signal",
            "title": "Recover svc-b",
            "confidence": 0.9,
            "run_id": "run-2",
            "recorded_at": now,
        }
    ]

    section = build_fleet_evidence_section(
        records,
        outcomes=outcomes,
        recommendation_metadata=metadata,
        generated_at=789.0,
    )

    assert section["outcome_counts"]["rec-1"]["resolved"] == 5
    assert "fleet_recovery" in section["trust_by_type"]
    assert section["trust_by_type"]["fleet_recovery"]["trust_score"] > 0
    assert "Incidents: `inc-1`" in section["markdown"]
    assert "`rec-1` category=`fleet_recovery` resolved=5" in section["markdown"]
    assert "trust=" in section["markdown"]


def test_fleet_evidence_section_omits_parallel_outcomes_when_none_linked():
    records = [
        {
            "run_id": "run-3",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-c"},
            "created_at": 100.0,
        }
    ]

    section = build_fleet_evidence_section(records)

    assert "Recommendation outcomes: `none linked`" in section["markdown"]
