from uar.core.evidence_pack_correlation_section import (
    build_correlation_evidence_section,
)


def test_correlation_section_empty_is_explicitly_unavailable():
    section = build_correlation_evidence_section([], generated_at=123.0)

    assert section["section"] == "recurrence_correlation_evidence"
    assert section["available"] is False
    assert section["correlations"] == []
    assert "Correlation: `unavailable`" in section["markdown"]


def test_correlation_section_preserves_existing_correlation_fields():
    section = build_correlation_evidence_section(
        [
            {
                "recommendation_id": "rec-1",
                "run_id": "run-1",
                "outcome_type": "resolved",
                "trust_delta": 0.09,
                "later_recurrence_count": 0,
                "later_recurrence_run_ids": [],
                "correlation_status": "no_later_recurrence",
                "evidence_refs": ["run:run-1"],
            }
        ],
        generated_at=456.0,
    )

    assert section["available"] is True
    assert section["correlations"][0]["recommendation_id"] == "rec-1"
    assert section["correlations"][0]["run_id"] == "run-1"
    assert section["correlations"][0]["later_recurrence_count"] == 0
    assert (
        section["correlations"][0]["correlation_status"]
        == "no_later_recurrence"
    )
    assert "Recommendation: `rec-1`" in section["markdown"]
    assert "Correlation: `no_later_recurrence`" in section["markdown"]
    assert "Later recurrence count: `0`" in section["markdown"]
