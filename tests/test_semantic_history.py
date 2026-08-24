import base64
from copy import deepcopy

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from uar.core.semantic_history import (
    CORPUS_SCHEMA,
    HistoryGateThresholds,
    review_semantic_history as _review_semantic_history,
)
from uar.core.semantic_history_attestation import (
    build_history_attestation_manifest,
    canonical_json_bytes,
)
from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_trace import projected_event_hash

_ATTESTOR_KEY_ID = "test-history-attestor"
_ATTESTOR_PRIVATE_KEY = Ed25519PrivateKey.generate()
_ATTESTOR_PUBLIC_KEY = _ATTESTOR_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
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
                        "pair_id": f"{split}-{index}",
                        "split": split,
                        "cohort": cohort,
                        "event_mode": "raw_runtime",
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
            "code_revision": "git:test-revision",
            "capture_window": {
                "start": "2026-08-01T00:00:00Z",
                "end": "2026-08-02T00:00:00Z",
            },
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
        "max_paired_different_rate": 0.0,
        "max_paired_indeterminate_rate": 0.0,
    }
    values.update(changes)
    return HistoryGateThresholds(**values)


def _attest(payload, thresholds):
    manifest = build_history_attestation_manifest(
        payload,
        key_id=_ATTESTOR_KEY_ID,
        review_policy={
            "min_samples_per_cohort": thresholds.min_samples_per_cohort,
            "max_js_divergence_bits": thresholds.max_js_divergence_bits,
            "max_total_variation": thresholds.max_total_variation,
            "max_telemetry_loss_rate": thresholds.max_telemetry_loss_rate,
            "max_telemetry_loss_delta": thresholds.max_telemetry_loss_delta,
            "max_paired_different_rate": thresholds.max_paired_different_rate,
            "max_paired_indeterminate_rate": (
                thresholds.max_paired_indeterminate_rate
            ),
        },
    )
    payload["attestation"] = {
        "manifest": manifest,
        "signature": base64.b64encode(
            _ATTESTOR_PRIVATE_KEY.sign(canonical_json_bytes(manifest))
        ).decode("ascii"),
    }


def _review(payload, *, thresholds):
    _attest(payload, thresholds)
    return _review_semantic_history(
        payload,
        thresholds=thresholds,
        trusted_attestor_public_keys={_ATTESTOR_KEY_ID: _ATTESTOR_PUBLIC_KEY},
    )


def test_observed_sanitized_corpus_passes_untouched_holdout():
    report = _review(_corpus(), thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is True
    assert report["gate_passes"] is True
    assert report["verdict"] == "PASS"
    assert {row["split"] for row in report["strata"]} == {
        "calibration",
        "holdout",
    }


def test_probability_plane_corpus_cannot_impersonate_operational_history():
    payload = _corpus()
    payload["provenance"]["source_kind"] = "probability_experiment"
    payload["provenance"]["model_generated"] = True

    report = _review(payload, thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is False
    assert report["gate_passes"] is False
    assert report["verdict"] == "HOLD"
    assert "source_not_observed_operational" in report["eligibility_reasons"]
    assert "model_generated_not_false" in report["eligibility_reasons"]


def test_calibration_only_corpus_cannot_close_holdout_gate():
    payload = _corpus()
    payload["runs"] = [
        run for run in payload["runs"] if run["split"] == "calibration"
    ]

    report = _review(payload, thresholds=_thresholds())

    assert report["gate_passes"] is False
    assert report["verdict"] == "HOLD"
    assert "missing_holdout_split" in report["eligibility_reasons"]


def test_holdout_distribution_drift_fails_even_when_calibration_is_green():
    payload = _corpus()
    for run in payload["runs"]:
        if run["split"] == "holdout" and run["cohort"] == "candidate":
            run["events"] = _events(result=2)

    report = _review(payload, thresholds=_thresholds())
    holdout = next(
        row for row in report["strata"] if row["split"] == "holdout"
    )

    assert holdout["distribution_ok"] is False
    assert report["gate_passes"] is False
    assert report["verdict"] == "FAIL"


def test_measured_telemetry_loss_fails_gate():
    payload = _corpus()
    for run in payload["runs"]:
        if run["split"] == "holdout" and run["cohort"] == "candidate":
            run["events"] = _events(omit_decision=True)

    report = _review(payload, thresholds=_thresholds())
    holdout = next(
        row for row in report["strata"] if row["split"] == "holdout"
    )

    assert holdout["candidate_telemetry_loss_rate"] == 1.0
    assert holdout["telemetry_ok"] is False
    assert report["gate_passes"] is False
    assert report["verdict"] == "FAIL"


def test_duplicate_run_ids_are_not_release_eligible():
    payload = _corpus()
    payload["runs"][1]["run_id"] = payload["runs"][0]["run_id"]

    report = _review(payload, thresholds=_thresholds())

    assert report["eligible_for_release_gate"] is False
    assert "duplicate_run_ids" in report["eligibility_reasons"]
    assert report["verdict"] == "FAIL"


def test_underpowered_holdout_is_reported_but_cannot_pass():
    report = _review(
        _corpus(samples=1), thresholds=_thresholds(min_samples_per_cohort=2)
    )
    holdout = next(
        row for row in report["strata"] if row["split"] == "holdout"
    )

    assert report["eligible_for_release_gate"] is True
    assert holdout["enough_samples"] is False
    assert report["gate_passes"] is False
    assert report["verdict"] == "HOLD"


def test_marginal_equivalence_cannot_hide_paired_semantic_reassignment():
    payload = _corpus()
    for run in payload["runs"]:
        if run["split"] != "holdout":
            continue
        pair_index = int(run["pair_id"].rsplit("-", 1)[1])
        baseline_result = 1 if pair_index == 0 else 2
        result = (
            baseline_result
            if run["cohort"] == "baseline"
            else 3 - baseline_result
        )
        run["events"] = _events(result=result)

    report = _review(payload, thresholds=_thresholds())
    holdout = next(
        row for row in report["strata"] if row["split"] == "holdout"
    )

    assert holdout["js_divergence_bits"] == 0.0
    assert holdout["total_variation"] == 0.0
    assert holdout["paired_different_rate"] == 1.0
    assert holdout["coupling_ok"] is False
    assert report["verdict"] == "FAIL"


def test_raw_mode_rejects_injected_semantic_events():
    payload = _corpus()
    payload["runs"][0]["events"] = list(
        observe_runtime_semantics(payload["runs"][0]["events"])
    )

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "raw_runtime_contains_semantic_events"
        for issue in report["integrity_issues"]
    )


def test_preshadowed_mode_requires_matching_runtime_projection_hash():
    payload = _corpus()
    run = payload["runs"][0]
    runtime_events = tuple(run["events"])
    run["event_mode"] = "preshadowed"
    run["events"] = list(observe_runtime_semantics(runtime_events))
    run["runtime_projection_hash"] = projected_event_hash(runtime_events)

    report = _review(payload, thresholds=_thresholds())
    assert report["verdict"] == "PASS"

    run["runtime_projection_hash"] = "tampered"
    report = _review(payload, thresholds=_thresholds())
    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "preshadowed_projection_hash_mismatch"
        for issue in report["integrity_issues"]
    )


def test_preshadowed_mode_rejects_forged_semantic_derivation():
    payload = _corpus()
    run = payload["runs"][0]
    runtime_events = tuple(run["events"])
    shadow_events = [
        deepcopy(event) for event in observe_runtime_semantics(runtime_events)
    ]
    for event in shadow_events:
        if event.get("type") == "semantic_result":
            event["payload"]["result_id"] = "forged"
    run["event_mode"] = "preshadowed"
    run["events"] = shadow_events
    run["runtime_projection_hash"] = projected_event_hash(runtime_events)

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "preshadowed_semantic_derivation_mismatch"
        for issue in report["integrity_issues"]
    )


def test_incomplete_runtime_history_cannot_pass():
    payload = _corpus()
    payload["runs"][0]["events"] = [{"type": "start", "payload": {}}]

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "runtime_complete_count_invalid"
        for issue in report["integrity_issues"]
    )


def test_witnessed_pair_difference_fails_even_when_underpowered():
    payload = _corpus(samples=1)
    for run in payload["runs"]:
        if run["split"] == "holdout" and run["cohort"] == "candidate":
            run["events"] = _events(result=2)

    report = _review(
        payload,
        thresholds=_thresholds(min_samples_per_cohort=2),
    )

    assert report["verdict"] == "FAIL"


def test_non_object_event_fails_instead_of_crashing_review():
    payload = _corpus()
    payload["runs"][0]["events"].insert(1, "not-an-event")

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "event_not_object"
        for issue in report["integrity_issues"]
    )


def test_orphan_skill_completion_cannot_synthesize_valid_history():
    payload = _corpus()
    payload["runs"][0]["events"] = [
        {"type": "start", "payload": {}},
        {
            "type": "skill_complete",
            "skill": "orphan",
            "payload": {"result": {"answer": 1}},
        },
        {
            "type": "complete",
            "payload": {
                "status": "completed",
                "outputs": [{"answer": 1}],
                "final_context": {},
            },
        },
    ]

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "orphan_skill_terminal_event"
        for issue in report["integrity_issues"]
    )


def test_duplicate_or_nonterminal_complete_event_is_rejected():
    payload = _corpus()
    payload["runs"][0]["events"].insert(
        1,
        {
            "type": "complete",
            "payload": {
                "status": "completed",
                "outputs": [],
                "final_context": {},
            },
        },
    )

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "runtime_complete_count_invalid"
        for issue in report["integrity_issues"]
    )


def test_preshadowed_duplicate_decision_event_is_rejected():
    payload = _corpus()
    run = payload["runs"][0]
    runtime_events = tuple(run["events"])
    shadow_events = list(observe_runtime_semantics(runtime_events))
    decision_index = next(
        index
        for index, event in enumerate(shadow_events)
        if event.get("type") == "candidate_admitted"
    )
    forged = deepcopy(shadow_events[decision_index])
    forged["type"] = "candidate_rejected"
    shadow_events.insert(decision_index, forged)
    run["event_mode"] = "preshadowed"
    run["events"] = shadow_events
    run["runtime_projection_hash"] = projected_event_hash(runtime_events)

    report = _review(payload, thresholds=_thresholds())

    assert report["verdict"] == "FAIL"
    assert any(
        issue["code"] == "preshadowed_semantic_derivation_mismatch"
        for issue in report["integrity_issues"]
    )


def test_unsigned_corpus_cannot_close_release_gate():
    report = _review_semantic_history(
        _corpus(),
        thresholds=_thresholds(),
        trusted_attestor_public_keys={_ATTESTOR_KEY_ID: _ATTESTOR_PUBLIC_KEY},
    )

    assert report["attestation_valid"] is False
    assert report["gate_passes"] is False
    assert report["verdict"] == "HOLD"
    assert "missing_signed_attestation" in report["eligibility_reasons"]


def test_signed_census_detects_pair_relabeling_after_collection():
    payload = _corpus()
    thresholds = _thresholds()
    _attest(payload, thresholds)
    payload["runs"][0]["pair_id"] = "concealed-reassignment"

    report = _review_semantic_history(
        payload,
        thresholds=thresholds,
        trusted_attestor_public_keys={_ATTESTOR_KEY_ID: _ATTESTOR_PUBLIC_KEY},
    )

    assert report["attestation_valid"] is False
    assert report["verdict"] == "FAIL"
    assert "attestation_manifest_mismatch" in report["eligibility_reasons"]


def test_signed_census_is_bound_to_review_policy():
    payload = _corpus()
    signed_thresholds = _thresholds()
    _attest(payload, signed_thresholds)

    report = _review_semantic_history(
        payload,
        thresholds=_thresholds(max_total_variation=1.0),
        trusted_attestor_public_keys={_ATTESTOR_KEY_ID: _ATTESTOR_PUBLIC_KEY},
    )

    assert report["attestation_valid"] is False
    assert report["verdict"] == "FAIL"
    assert "attestation_manifest_mismatch" in report["eligibility_reasons"]


def test_invalid_thresholds_fail_closed():
    for changes, reason in (
        (
            {"min_samples_per_cohort": 0},
            "invalid_min_samples_per_cohort",
        ),
        (
            {"max_total_variation": float("nan")},
            "invalid_max_total_variation",
        ),
        (
            {"max_paired_different_rate": -0.1},
            "invalid_max_paired_different_rate",
        ),
    ):
        thresholds = _thresholds(**changes)
        report = _review(_corpus(), thresholds=thresholds)
        assert report["verdict"] == "FAIL"
        assert reason in report["eligibility_reasons"]
