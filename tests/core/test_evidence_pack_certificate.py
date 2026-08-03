from copy import deepcopy

from uar.core.evidence_pack_certificate import (
    audit_evidence_pack_certificate,
    audit_evidence_pack_ordinary,
    compare_evidence_pack_audits,
)


def _valid_pack():
    return {
        "title": "UAR Evidence Pack v2",
        "version": "v2",
        "sections": [
            {
                "section": "fleet_signal_evidence",
                "summary": {
                    "status": "critical",
                    "signals": [
                        {
                            "linkage": {
                                "replay": {"run_id": "r2", "available": True},
                                "evidence_refs": ["run:r2", "incident:i1"],
                            }
                        }
                    ],
                },
                "trust_by_type": {"repair": {"trust_score": 0.8}},
            },
            {
                "section": "incident_intelligence_evidence",
                "summary": {
                    "status": "active",
                    "patterns": [
                        {
                            "recurrence_count": 2,
                            "affected_run_ids": ["r1", "r2"],
                            "evidence_refs": ["run:r1", "run:r2"],
                        }
                    ],
                },
            },
            {
                "section": "recurrence_correlation_evidence",
                "available": True,
                "correlations": [
                    {
                        "recommendation_id": "rec-1",
                        "run_id": "r1",
                        "correlation_status": "later_recurrence",
                        "later_recurrence_count": 1,
                        "later_recurrence_run_ids": ["r2"],
                        "evidence_refs": ["run:r1", "run:r2"],
                    }
                ],
            },
        ],
    }


def test_valid_pack_is_admissible_under_both_disciplines():
    pack = _valid_pack()

    assert audit_evidence_pack_ordinary(pack).admissible is True
    assert audit_evidence_pack_certificate(pack).admissible is True


def test_certificate_catches_missing_cross_field_lineage_beyond_ordinary_shape():
    pack = _valid_pack()
    pack["sections"][2]["correlations"][0]["evidence_refs"] = ["run:r1"]

    comparison = compare_evidence_pack_audits(pack)

    assert comparison.ordinary.admissible is True
    assert comparison.certificate.admissible is False
    assert "missing_correlation_lineage" in comparison.certificate.codes()
    assert any(
        item.code == "missing_correlation_lineage"
        for item in comparison.certificate_only
    )


def test_certificate_catches_duplicate_inflation_beyond_ordinary_shape():
    pack = _valid_pack()
    pack["sections"][2]["correlations"][0]["evidence_refs"].append("run:r2")

    comparison = compare_evidence_pack_audits(pack)

    assert comparison.ordinary.admissible is True
    assert "duplicate_evidence_reference" in comparison.certificate.codes()


def test_certificate_catches_recurrence_status_and_count_conflicts():
    pack = _valid_pack()
    correlation = pack["sections"][2]["correlations"][0]
    correlation["correlation_status"] = "no_later_recurrence"
    correlation["later_recurrence_count"] = 2

    audit = audit_evidence_pack_certificate(pack)

    assert "recurrence_count_mismatch" in audit.codes()
    assert "status_recurrence_conflict" in audit.codes()


def test_certificate_catches_available_replay_without_lineage():
    pack = _valid_pack()
    pack["sections"][0]["summary"]["signals"][0]["linkage"][
        "evidence_refs"
    ] = ["incident:i1"]

    comparison = compare_evidence_pack_audits(pack)

    assert comparison.ordinary.admissible is True
    assert "missing_replay_lineage" in comparison.certificate.codes()


def test_ordinary_and_certificate_both_reject_missing_required_section():
    pack = _valid_pack()
    pack["sections"] = pack["sections"][:2]

    ordinary = audit_evidence_pack_ordinary(pack)
    certificate = audit_evidence_pack_certificate(pack)

    assert "missing_required_section" in ordinary.codes()
    assert "missing_required_section" in certificate.codes()


def test_ordinary_rejects_out_of_range_trust_score():
    pack = deepcopy(_valid_pack())
    pack["sections"][0]["trust_by_type"]["repair"]["trust_score"] = 1.5

    ordinary = audit_evidence_pack_ordinary(pack)

    assert "trust_score_out_of_range" in ordinary.codes()
