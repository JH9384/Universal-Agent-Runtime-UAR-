from copy import deepcopy

import pytest

from uar.core.evidence_pack_validation_corpus import (
    corpus_cases_from_document,
    evaluate_evidence_pack_corpus_document,
    render_evidence_pack_corpus_report,
)


def _pack():
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
                                "evidence_refs": ["run:r2"],
                            }
                        }
                    ],
                },
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


def _document():
    reference = _pack()
    current = deepcopy(reference)
    current["sections"] = current["sections"][:2]
    ordinary = deepcopy(reference)
    ordinary["sections"][2]["correlations"][0]["evidence_refs"] = ["run:r1"]
    return {
        "corpus_id": "seed-corpus",
        "cases": [
            {
                "case_id": "lineage-loss",
                "reference_name": "adjudicated-reference",
                "reference_pack": reference,
                "provenance": "synthetic",
                "arms": [
                    {"name": "current", "pack": current},
                    {"name": "ordinary_validation", "pack": ordinary},
                    {"name": "certificate", "pack": deepcopy(reference)},
                ],
            }
        ],
    }


def test_corpus_document_evaluates_semantics_and_certificate_coverage():
    result = evaluate_evidence_pack_corpus_document(_document())

    assert result.corpus_id == "seed-corpus"
    assert result.classification_counts == {"exact_reference_reconstruction": 1}
    assert result.certificate_only_obstruction_count >= 1

    case = result.cases[0]
    audits = case.audit_by_name()
    assert audits["ordinary_validation"].audit.ordinary.admissible is True
    assert audits["ordinary_validation"].audit.certificate.admissible is False
    assert case.trial.by_name()["certificate"].semantic_distance == 0.0

    report = render_evidence_pack_corpus_report(result)
    assert "# FCRL v4 Corpus Report — seed-corpus" in report
    assert "lineage-loss" in report
    assert "exact_reference_reconstruction" in report


def test_corpus_document_rejects_duplicate_case_ids():
    document = _document()
    document["cases"].append(deepcopy(document["cases"][0]))

    with pytest.raises(ValueError, match="duplicate case_id"):
        corpus_cases_from_document(document)


def test_corpus_document_requires_exact_three_arm_set():
    document = _document()
    document["cases"][0]["arms"] = document["cases"][0]["arms"][:2]

    with pytest.raises(ValueError, match="arm set mismatch"):
        corpus_cases_from_document(document)
