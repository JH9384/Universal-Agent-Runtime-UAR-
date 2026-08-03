from copy import deepcopy

from uar.core.evidence_pack_validation import (
    ValidationArm,
    classify_certificate_leverage,
    compare_evidence_packs,
    evaluate_validation_trial,
    render_validation_report,
)


def _reference_pack():
    return {
        "title": "UAR Evidence Pack v2",
        "version": "v2",
        "generated_at": 100.0,
        "sections": [
            {
                "section": "fleet_signal_evidence",
                "summary": {
                    "status": "critical",
                    "signals": [
                        {
                            "linkage": {
                                "evidence_refs": ["run:r1", "incident:i1"],
                                "replay": {"run_id": "r2"},
                            }
                        }
                    ],
                },
                "trust_by_type": {
                    "repair": {"trust_score": 0.8},
                },
            },
            {
                "section": "incident_intelligence_evidence",
                "summary": {
                    "status": "active",
                    "patterns": [
                        {
                            "recurrence_count": 2,
                            "latest_run_id": "r2",
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


def test_compare_evidence_packs_exact_reference():
    reference = _reference_pack()

    discrepancy = compare_evidence_packs(reference, deepcopy(reference))

    assert discrepancy.exact is True
    assert discrepancy.semantic_distance() == 0.0
    assert discrepancy.to_dict()["missing_evidence_refs"] == []


def test_compare_evidence_packs_retains_lineage_and_status_vector():
    reference = _reference_pack()
    candidate = deepcopy(reference)
    candidate["sections"][0]["summary"]["status"] = "warning"
    candidate["sections"][0]["summary"]["signals"][0]["linkage"][
        "evidence_refs"
    ] = ["run:r1"]
    candidate["sections"][1]["summary"]["patterns"][0][
        "recurrence_count"
    ] = 1
    candidate["sections"][2]["available"] = False
    candidate["sections"][2]["correlations"][0]["later_recurrence_run_ids"] = []

    discrepancy = compare_evidence_packs(reference, candidate)

    assert (
        "sections/fleet_signal_evidence/summary/status"
        in discrepancy.status_mismatches
    )
    assert discrepancy.availability_mismatches == (
        "recurrence_correlation_evidence",
    )
    assert any(
        item.endswith("=incident:i1") for item in discrepancy.missing_evidence_refs
    )
    assert any(
        "later_recurrence_run_ids=r2" in item
        for item in discrepancy.missing_run_refs
    )
    assert discrepancy.recurrence_count_abs_error == 1
    assert discrepancy.semantic_distance() > 0.0


def test_compare_evidence_packs_detects_duplicate_reference_inflation():
    reference = _reference_pack()
    candidate = deepcopy(reference)
    refs = candidate["sections"][2]["correlations"][0]["evidence_refs"]
    refs.append("run:r2")

    discrepancy = compare_evidence_packs(reference, candidate)

    assert any(item.endswith("=run:r2") for item in discrepancy.extra_evidence_refs)
    assert discrepancy.semantic_distance() >= 4.0


def test_validation_trial_compares_current_ordinary_and_certificate_arms():
    reference = _reference_pack()

    current = deepcopy(reference)
    current["sections"] = current["sections"][:2]

    ordinary = deepcopy(reference)
    ordinary["sections"][0]["summary"]["signals"][0]["linkage"][
        "evidence_refs"
    ] = ["run:r1"]

    certificate = deepcopy(reference)

    result = evaluate_validation_trial(
        reference_name="reference_exhaustive",
        reference_pack=reference,
        arms=[
            ValidationArm("current", current, runtime_ms=2.0, storage_bytes=500),
            ValidationArm(
                "ordinary_validation",
                ordinary,
                runtime_ms=2.5,
                storage_bytes=550,
            ),
            ValidationArm(
                "certificate",
                certificate,
                runtime_ms=4.0,
                storage_bytes=800,
                notes=("synthetic exact reconstruction",),
            ),
        ],
    )

    by_name = result.by_name()
    assert by_name["current"].semantic_distance > 0.0
    assert by_name["ordinary_validation"].semantic_distance > 0.0
    assert by_name["certificate"].semantic_distance == 0.0
    assert classify_certificate_leverage(result) == "exact_reference_reconstruction"

    markdown = render_validation_report(result)
    assert "# FCRL v4 Evidence Pack Validation" in markdown
    assert "`certificate` | 0.000000 | `True`" in markdown
    assert "Missing evidence refs" in markdown


def test_certificate_leverage_reports_no_gain_when_tied():
    reference = _reference_pack()
    candidate = deepcopy(reference)
    candidate["sections"] = candidate["sections"][:2]

    result = evaluate_validation_trial(
        reference_name="reference",
        reference_pack=reference,
        arms=[
            ValidationArm("current", candidate),
            ValidationArm("ordinary_validation", candidate),
            ValidationArm("certificate", candidate),
        ],
    )

    assert classify_certificate_leverage(result) == "no_semantic_leverage"
