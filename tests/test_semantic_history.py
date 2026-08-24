from uar.core.semantic_history import (
    CORPUS_SCHEMA,
    HistoryGateThresholds,
    review_semantic_history,
)


def _events(*, result=1, omit_decision=False):
    events = [
        {"type": "start", "payload": {}},
        {"type": "skill_start", "skill": "decide", "payload": {}},
    ]
    if not omit_decision:
        events.append(
            {
                "type": "skill_complete",
                "skill": "decide",
                "payload": {"result": {"answer": result}},
            }
        )
    events.append(
        {
            "type": "complete",
            "payload": {
                "status": "completed",
                "outputs": [{"answer": result}],
                "final_context": {},
            },
        }
    )
    return events


def _corpus(samples=2):
    runs = []
    for split in ("calibration", "holdout"):
        for cohort in ("baseline", "candidate"):
            for index in range(samples):
                runs.append(
                    {
                        "run_id": f"{split}-{cohort}-{index}",
                        "split": split,
                        "cohort": cohort,
                        "task_class": "decision",
                        "final_result_class": "success",
                        "events": _events(),
                    }
                )
    return {
        "schema": CORPUS_SCHEMA,
        "provenance": {
            "source_kind": "observed_operational",
            "model_generated": False,
            "sanitized": True,
            "sanitization": {
                "method": "allowlist-v1",
                "reviewed_by": "release-reviewer",
                "source_snapshot": "sha256:history-snapshot",
            },
        },
        "runs": runs,
    }


def _thresholds(**changes):
    values = {
        "min_samples_per_cohort": 2,
        "max_js_divergence_bits": 0.02,
        "max_total_variation": 0.05,
        "max_telemetry_loss_rate": 0.01,
        "max_telemetry_loss_delta": 0.005,
    }
    values.update(changes)
    return HistoryGateThresholds(**values)


def test_observed_sanitized_corpus_passes_untouched_holdout():
    report = review_semantic_history(_corpus(), thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is True
    assert report["gate_passes"] is True
    assert {row["split"] for row in report["strata"]} == {
        "calibration",
        "holdout",
    }


def test_probability_plane_corpus_cannot_impersonate_operational_history():
    payload = _corpus()
    payload["provenance"]["source_kind"] = "probability_experiment"
    payload["provenance"]["model_generated"] = True

    report = review_semantic_history(payload, thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is False
    assert report["gate_passes"] is False
    assert "source_not_observed_operational" in report["eligibility_reasons"]
    assert "model_generated_not_false" in report["eligibility_reasons"]


def test_calibration_only_corpus_cannot_close_holdout_gate():
    payload = _corpus()
    payload["runs"] = [
        run for run in payload["runs"] if run["split"] == "calibration"
    ]

    report = review_semantic_history(payload, thresholds=_thresholds())

    assert report["gate_passes"] is False
    assert "missing_holdout_split" in report["eligibility_reasons"]


def test_holdout_distribution_drift_fails_even_when_calibration_is_green():
    payload = _corpus()
    for run in payload["runs"]:
        if run["split"] == "holdout" and run["cohort"] == "candidate":
            run["events"] = _events(result=2)

    report = review_semantic_history(payload, thresholds=_thresholds())
    holdout = next(row for row in report["strata"] if row["split"] == "holdout")

    assert holdout["distribution_ok"] is False
    assert report["gate_passes"] is False


def test_measured_telemetry_loss_fails_gate():
    payload = _corpus()
    for run in payload["runs"]:
        if run["split"] == "holdout" and run["cohort"] == "candidate":
            run["events"] = _events(omit_decision=True)

    report = review_semantic_history(payload, thresholds=_thresholds())
    holdout = next(row for row in report["strata"] if row["split"] == "holdout")

    assert holdout["candidate_telemetry_loss_rate"] == 1.0
    assert holdout["telemetry_ok"] is False
    assert report["gate_passes"] is False


def test_duplicate_run_ids_are_not_release_eligible():
    payload = _corpus()
    payload["runs"][1]["run_id"] = payload["runs"][0]["run_id"]

    report = review_semantic_history(payload, thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is False
    assert "duplicate_run_ids" in report["eligibility_reasons"]


def test_underpowered_holdout_is_reported_but_cannot_pass():
    report = review_semantic_history(
        _corpus(samples=1), thresholds=_thresholds(min_samples_per_cohort=2)
    )
    holdout = next(row for row in report["strata"] if row["split"] == "holdout")

    assert report["eligible_for_release_gate"] is True
    assert holdout["enough_samples"] is False
    assert report["gate_passes"] is False
