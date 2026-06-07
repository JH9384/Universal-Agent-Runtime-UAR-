"""Tests for D4C incident evidence section."""

from uar.core.incident_evidence_section import build_incident_evidence_section


def test_incident_evidence_section_nominal_without_patterns():
    section = build_incident_evidence_section([], generated_at=123.0)

    assert section["section"] == "incident_intelligence_evidence"
    assert section["summary"]["status"] == "nominal"
    assert "Incident Intelligence Evidence" in section["markdown"]
    assert "No recurring incident patterns were detected." in section["markdown"]


def test_incident_evidence_section_includes_recurring_pattern():
    records = [
        {
            "run_id": "r1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-a", "incident_id": "inc-1"},
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-a", "recommendation_id": "rec-1"},
            "created_at": 200.0,
        },
    ]
    outcomes = [
        {"recommendation_id": "rec-1", "outcome_type": "recurred"},
    ]

    section = build_incident_evidence_section(
        records,
        outcomes=outcomes,
        generated_at=456.0,
    )

    assert section["summary"]["status"] == "active"
    assert section["summary"]["recurring_patterns"] == 1
    assert "service:svc-a" in section["markdown"]
    assert "Latest run: `r2`" in section["markdown"]
    assert "Incident IDs: `inc-1`" in section["markdown"]
    assert "Recommendation IDs: `rec-1`" in section["markdown"]
    assert "`rec-1` resolved=0 recurred=1 unknown=0" in section["markdown"]
