"""Tests for D4C Phase 3 incident intelligence summary."""

import time

from uar.core.incident_intelligence import build_incident_intelligence_summary


def test_incident_intelligence_nominal_without_recurrence():
    summary = build_incident_intelligence_summary(
        [
            {
                "run_id": "r1",
                "status": "failed",
                "skills": ["echo"],
                "metadata": {"service": "svc-a"},
            }
        ]
    )

    assert summary["status"] == "nominal"
    assert summary["recurring_patterns"] == 0
    assert summary["total_failures"] == 1
    assert summary["top_pattern"] is None


def test_incident_intelligence_detects_recurrence_by_service():
    records = [
        {
            "run_id": "r1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-a"},
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-a"},
            "created_at": 200.0,
        },
    ]

    summary = build_incident_intelligence_summary(records)
    top = summary["top_pattern"]

    assert summary["status"] == "active"
    assert summary["recurring_patterns"] == 1
    assert top["scope"] == "service"
    assert top["value"] == "svc-a"
    assert top["recurrence_count"] == 2
    assert top["affected_run_ids"] == ["r2", "r1"]
    assert top["latest_run_id"] == "r2"
    assert top["evidence_refs"] == ["run:r2", "run:r1"]


def test_incident_intelligence_carries_links_and_outcomes():
    now = time.time()
    records = [
        {
            "run_id": "r1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {
                "service": "svc-b",
                "incident_id": "inc-1",
                "recommendation_id": "rec-1",
            },
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {
                "service": "svc-b",
                "incident_ids": ["inc-1", "inc-2"],
                "recommendation_ids": ["rec-1", "rec-2"],
            },
            "created_at": 200.0,
        },
    ]
    outcomes = [
        {
            "recommendation_id": "rec-1",
            "outcome_type": "resolved",
            "recorded_at": now,
        },
        {
            "recommendation_id": "rec-1",
            "outcome_type": "recurred",
            "recorded_at": now,
        },
        {
            "recommendation_id": "rec-2",
            "outcome_type": "unknown",
            "recorded_at": now,
        },
    ]

    summary = build_incident_intelligence_summary(records, outcomes=outcomes)
    top = summary["top_pattern"]

    assert top["linked_incident_ids"] == ["inc-1", "inc-2"]
    assert top["linked_recommendation_ids"] == ["rec-1", "rec-2"]
    assert top["outcome_counts"]["rec-1"] == {
        "resolved": 1,
        "recurred": 1,
        "unknown": 0,
    }
    assert top["outcome_counts"]["rec-2"] == {
        "resolved": 0,
        "recurred": 0,
        "unknown": 1,
    }


def test_incident_intelligence_reuses_existing_trust_engine_by_category():
    now = time.time()
    records = [
        {
            "run_id": "r1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-c", "recommendation_id": "rec-1"},
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-c", "recommendation_id": "rec-1"},
            "created_at": 200.0,
        },
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
            "confidence": 0.85,
            "recorded_at": now,
        }
    ]

    summary = build_incident_intelligence_summary(
        records,
        outcomes=outcomes,
        recommendation_metadata=metadata,
    )
    top = summary["top_pattern"]

    assert "fleet_recovery" in top["trust_by_type"]
    assert top["trust_by_type"]["fleet_recovery"]["trust_score"] > 0


def test_incident_intelligence_handles_fallback_and_missing_data():
    records = [
        {
            "run_id": "r1",
            "status": "failed",
            "skills": ["parse_pdf"],
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "status": "failed",
            "skills": ["parse_pdf"],
            "created_at": 200.0,
        },
    ]

    summary = build_incident_intelligence_summary(records)
    top = summary["top_pattern"]

    assert top["scope"] == "skill"
    assert top["value"] == "parse_pdf"
    assert top["linked_incident_ids"] == []
    assert top["linked_recommendation_ids"] == []
    assert top["outcome_counts"] == {}
    assert top["trust_by_type"] == {}
