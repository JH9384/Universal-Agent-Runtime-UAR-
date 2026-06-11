"""Tests for reuse-first Evidence Pack v2 composer."""

from uar.core.evidence_pack_v2 import compose_evidence_pack_v2


def test_compose_evidence_pack_v2_includes_fleet_and_incident_sections():
    pack = compose_evidence_pack_v2([], generated_at=123.0)

    assert pack["title"] == "UAR Evidence Pack v2"
    assert pack["version"] == "v2"
    assert pack["generated_at"] == 123.0
    section_names = [section["section"] for section in pack["sections"]]
    assert section_names == [
        "fleet_signal_evidence",
        "incident_intelligence_evidence",
        "recurrence_correlation_evidence",
    ]
    assert "# UAR Evidence Pack v2" in pack["markdown"]
    assert "## Fleet Signal Evidence" in pack["markdown"]
    assert "## Incident Intelligence Evidence" in pack["markdown"]


def test_compose_evidence_pack_v2_carries_fleet_signal_markdown():
    records = [
        {
            "run_id": "run-pack-1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-pack"},
            "created_at": 100.0,
        }
    ]

    pack = compose_evidence_pack_v2(records, generated_at=456.0)

    assert pack["sections"][0]["summary"]["status"] == "critical"
    assert "Service signal: svc-pack" in pack["markdown"]
    assert "Latest replay run: `run-pack-1`" in pack["markdown"]


def test_compose_evidence_pack_v2_carries_incident_recurrence_markdown():
    records = [
        {
            "run_id": "r1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-pack"},
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-pack"},
            "created_at": 200.0,
        },
    ]

    pack = compose_evidence_pack_v2(records, generated_at=789.0)

    assert pack["sections"][1]["summary"]["status"] == "active"
    assert "service:svc-pack" in pack["markdown"]
    assert "Recurrence count: `2`" in pack["markdown"]

def test_compose_evidence_pack_v2_includes_recurrence_correlation_section():
    pack = compose_evidence_pack_v2(
        [],
        generated_at=999.0,
        correlations=[
            {
                "recommendation_id": "rec-1",
                "run_id": "run-1",
                "outcome_type": "resolved",
                "later_recurrence_count": 0,
                "later_recurrence_run_ids": [],
                "correlation_status": "no_later_recurrence",
                "evidence_refs": ["run:run-1"],
            }
        ],
    )

    sections = {section["section"]: section for section in pack["sections"]}
    assert "recurrence_correlation_evidence" in sections
    assert sections["recurrence_correlation_evidence"]["available"] is True
    assert "Recurrence Correlation Evidence" in pack["markdown"]
    assert "Correlation: `no_later_recurrence`" in pack["markdown"]

