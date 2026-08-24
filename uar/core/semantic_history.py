"""Release-gate review for sanitized Semantic Replay history corpora.

Probability-plane experiments are useful for designing mutation strata, but
only observed operational UAR event history is eligible to close the real-
history exit criterion.  This module makes that boundary machine-checkable.
It is validation support and does not alter runtime behavior or Trust Spine
weights.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any

from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_history_attestation import verify_history_attestation
from uar.core.semantic_statistics import compare_semantic_distributions
from uar.core.semantic_trace import (
    SEMANTIC_EVENT_TYPES,
    ComparisonOutcome,
    compare_semantic_traces,
    project_nonsemantic_events,
    projected_event_hash,
    semantic_trace_from_events,
    validate_semantic_trace,
)

CORPUS_SCHEMA = "uar.semantic-history-corpus.v1"
ELIGIBLE_SOURCE_KIND = "observed_operational"


class HistoryGateVerdict(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class HistoryGateThresholds:
    min_samples_per_cohort: int = 20
    max_js_divergence_bits: float = 0.02
    max_total_variation: float = 0.05
    max_telemetry_loss_rate: float = 0.01
    max_telemetry_loss_delta: float = 0.005
    max_paired_different_rate: float = 0.0
    max_paired_indeterminate_rate: float = 0.0


DEFAULT_HISTORY_GATE_THRESHOLDS = HistoryGateThresholds()


def _threshold_issues(thresholds: HistoryGateThresholds) -> tuple[str, ...]:
    issues = []
    if (
        isinstance(thresholds.min_samples_per_cohort, bool)
        or not isinstance(thresholds.min_samples_per_cohort, int)
        or thresholds.min_samples_per_cohort < 1
    ):
        issues.append("invalid_min_samples_per_cohort")
    bounded = {
        "max_js_divergence_bits": thresholds.max_js_divergence_bits,
        "max_total_variation": thresholds.max_total_variation,
        "max_telemetry_loss_rate": thresholds.max_telemetry_loss_rate,
        "max_telemetry_loss_delta": thresholds.max_telemetry_loss_delta,
        "max_paired_different_rate": thresholds.max_paired_different_rate,
        "max_paired_indeterminate_rate": (
            thresholds.max_paired_indeterminate_rate
        ),
    }
    for name, value in bounded.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            issues.append(f"invalid_{name}")
    return tuple(issues)


def _validate_runtime_event_stream(
    events: Sequence[Mapping[str, Any]],
) -> None:
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("event_not_object")
    event_types = [str(event.get("type", "")) for event in events]
    if event_types.count("start") != 1:
        raise ValueError("runtime_start_count_invalid")
    if event_types.count("complete") != 1:
        raise ValueError("runtime_complete_count_invalid")
    if event_types[-1] != "complete":
        raise ValueError("runtime_complete_not_terminal")


def _trace(
    events: Sequence[Mapping[str, Any]],
    *,
    event_mode: str,
    expected_projection_hash: str | None = None,
):
    if any(not isinstance(event, Mapping) for event in events):
        raise ValueError("event_not_object")
    has_semantic_events = any(
        str(event.get("type", "")) in SEMANTIC_EVENT_TYPES for event in events
    )
    source = tuple(events)
    if event_mode == "raw_runtime":
        if has_semantic_events:
            raise ValueError("raw_runtime_contains_semantic_events")
        _validate_runtime_event_stream(source)
        source = observe_runtime_semantics(source)
    elif event_mode == "preshadowed":
        if not has_semantic_events:
            raise ValueError("preshadowed_missing_semantic_events")
        runtime_projection = project_nonsemantic_events(source)
        _validate_runtime_event_stream(runtime_projection)
        if not runtime_projection:
            raise ValueError("preshadowed_missing_runtime_projection")
        if not expected_projection_hash:
            raise ValueError("preshadowed_missing_projection_hash")
        if (
            projected_event_hash(runtime_projection)
            != expected_projection_hash
        ):
            raise ValueError("preshadowed_projection_hash_mismatch")
    else:
        raise ValueError("invalid_event_mode")
    trace = semantic_trace_from_events(source)
    if event_mode == "preshadowed":
        derived_events = observe_runtime_semantics(runtime_projection)
        provided_semantic_events = tuple(
            event
            for event in source
            if str(event.get("type", "")) in SEMANTIC_EVENT_TYPES
        )
        derived_semantic_events = tuple(
            event
            for event in derived_events
            if str(event.get("type", "")) in SEMANTIC_EVENT_TYPES
        )
        if provided_semantic_events != derived_semantic_events:
            raise ValueError("preshadowed_semantic_derivation_mismatch")
    if not trace.stages:
        raise ValueError("empty_semantic_trace")
    if trace.final_result is None:
        raise ValueError("missing_semantic_result")
    return trace


def _corpus_eligibility(payload: Mapping[str, Any]) -> tuple[str, ...]:
    reasons = []
    if payload.get("schema") != CORPUS_SCHEMA:
        reasons.append("schema_mismatch")
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        return tuple(reasons + ["missing_provenance"])
    if provenance.get("source_kind") != ELIGIBLE_SOURCE_KIND:
        reasons.append("source_not_observed_operational")
    if provenance.get("model_generated") is not False:
        reasons.append("model_generated_not_false")
    if provenance.get("sanitized") is not True:
        reasons.append("corpus_not_sanitized")
    if not provenance.get("code_revision"):
        reasons.append("missing_code_revision")
    capture_window = provenance.get("capture_window")
    if not isinstance(capture_window, Mapping):
        reasons.append("missing_capture_window")
    elif not capture_window.get("start") or not capture_window.get("end"):
        reasons.append("incomplete_capture_window")
    sanitization = provenance.get("sanitization")
    if not isinstance(sanitization, Mapping):
        reasons.append("missing_sanitization_record")
    else:
        for key in ("method", "reviewed_by", "source_snapshot"):
            if not sanitization.get(key):
                reasons.append(f"missing_sanitization_{key}")
    return tuple(reasons)


def review_semantic_history(
    payload: Mapping[str, Any],
    *,
    thresholds: HistoryGateThresholds = DEFAULT_HISTORY_GATE_THRESHOLDS,
    trusted_attestor_public_keys: Mapping[str, bytes] = {},
) -> dict[str, Any]:
    """Review an already-sanitized, pre-split runtime history corpus.

    Runs are grouped by ``split`` (``calibration`` or ``holdout``), task class,
    and final-result class.  Each stratum must contain baseline and candidate
    cohorts.  Release status is determined from the untouched holdout only;
    calibration results are reported but cannot close the gate.
    """

    threshold_issues = _threshold_issues(thresholds)
    eligibility_reasons = list(_corpus_eligibility(payload))
    eligibility_reasons.extend(threshold_issues)
    attestation_valid, attestation_reasons = verify_history_attestation(
        payload,
        review_policy=asdict(thresholds),
        trusted_public_keys=trusted_attestor_public_keys,
    )
    eligibility_reasons.extend(attestation_reasons)
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        eligibility_reasons.append("missing_runs")
        runs = []

    groups: dict[tuple[str, str, str], dict[str, list[Any]]] = defaultdict(
        lambda: {"baseline": [], "candidate": []}
    )
    pairs: dict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(dict)
    integrity_issues = []
    duplicate_ids = []
    seen_ids = set()

    for index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            integrity_issues.append(
                {"run_index": index, "code": "run_not_object"}
            )
            continue
        run_id = str(run.get("run_id", ""))
        if not run_id:
            integrity_issues.append(
                {"run_index": index, "code": "missing_run_id"}
            )
        elif run_id in seen_ids:
            duplicate_ids.append(run_id)
        seen_ids.add(run_id)

        split = str(run.get("split", ""))
        cohort = str(run.get("cohort", ""))
        task_class = str(run.get("task_class", ""))
        result_class = str(run.get("final_result_class", ""))
        pair_id = str(run.get("pair_id", ""))
        event_mode = str(run.get("event_mode", ""))
        if split not in {"calibration", "holdout"}:
            integrity_issues.append(
                {"run_id": run_id, "code": "invalid_split"}
            )
            continue
        if cohort not in {"baseline", "candidate"}:
            integrity_issues.append(
                {"run_id": run_id, "code": "invalid_cohort"}
            )
            continue
        if not task_class or not result_class:
            integrity_issues.append(
                {"run_id": run_id, "code": "missing_stratum"}
            )
            continue
        if not pair_id:
            integrity_issues.append(
                {"run_id": run_id, "code": "missing_pair_id"}
            )
            continue
        events = run.get("events")
        if not isinstance(events, list) or not events:
            integrity_issues.append(
                {"run_id": run_id, "code": "missing_events"}
            )
            continue

        try:
            trace = _trace(
                events,
                event_mode=event_mode,
                expected_projection_hash=run.get("runtime_projection_hash"),
            )
        except ValueError as exc:
            integrity_issues.append({"run_id": run_id, "code": str(exc)})
            continue
        issues = validate_semantic_trace(trace)
        for issue in issues:
            integrity_issues.append(
                {
                    "run_id": run_id,
                    "stage_id": issue.stage_id,
                    "code": issue.code,
                }
            )
        groups[(split, task_class, result_class)][cohort].append(trace)
        pair_key = (split, task_class, result_class, pair_id)
        if cohort in pairs[pair_key]:
            integrity_issues.append(
                {"run_id": run_id, "code": "duplicate_pair_cohort"}
            )
        else:
            pairs[pair_key][cohort] = trace

    if duplicate_ids:
        eligibility_reasons.append("duplicate_run_ids")
    if integrity_issues:
        eligibility_reasons.append("trace_integrity_issues")

    strata = []
    holdout_passes = []
    hard_failures = bool(
        integrity_issues or duplicate_ids or threshold_issues
    ) or (
        not attestation_valid
        and "missing_signed_attestation" not in attestation_reasons
    )
    for (split, task_class, result_class), cohorts in sorted(groups.items()):
        baseline = cohorts["baseline"]
        candidate = cohorts["candidate"]
        report = compare_semantic_distributions(baseline, candidate)
        baseline_loss = (
            sum(1.0 - trace.observation_ratio() for trace in baseline)
            / len(baseline)
            if baseline
            else None
        )
        candidate_loss = (
            sum(1.0 - trace.observation_ratio() for trace in candidate)
            / len(candidate)
            if candidate
            else None
        )
        enough_samples = (
            len(baseline) >= thresholds.min_samples_per_cohort
            and len(candidate) >= thresholds.min_samples_per_cohort
        )
        telemetry_ok = (
            baseline_loss is not None
            and candidate_loss is not None
            and baseline_loss <= thresholds.max_telemetry_loss_rate
            and candidate_loss <= thresholds.max_telemetry_loss_rate
            and abs(candidate_loss - baseline_loss)
            <= thresholds.max_telemetry_loss_delta
        )
        distribution_ok = (
            report.js_divergence_bits <= thresholds.max_js_divergence_bits
            and report.total_variation <= thresholds.max_total_variation
        )
        stratum_pairs = [
            value
            for (pair_split, pair_task, pair_result, _), value in pairs.items()
            if (pair_split, pair_task, pair_result)
            == (split, task_class, result_class)
        ]
        complete_pairs = [
            value
            for value in stratum_pairs
            if set(value) == {"baseline", "candidate"}
        ]
        incomplete_pair_count = len(stratum_pairs) - len(complete_pairs)
        paired_reports = [
            compare_semantic_traces(value["baseline"], value["candidate"])
            for value in complete_pairs
        ]
        paired_different = sum(
            report.outcome is ComparisonOutcome.DIFFERENT
            for report in paired_reports
        )
        paired_indeterminate = sum(
            report.outcome is ComparisonOutcome.INDETERMINATE
            for report in paired_reports
        )
        paired_count = len(paired_reports)
        paired_different_rate = (
            paired_different / paired_count if paired_count else None
        )
        paired_indeterminate_rate = (
            paired_indeterminate / paired_count if paired_count else None
        )
        coupling_ok = (
            incomplete_pair_count == 0
            and paired_count >= thresholds.min_samples_per_cohort
            and paired_different_rate is not None
            and paired_indeterminate_rate is not None
            and paired_different_rate <= thresholds.max_paired_different_rate
            and paired_indeterminate_rate
            <= thresholds.max_paired_indeterminate_rate
        )
        stratum_passes = (
            enough_samples and telemetry_ok and distribution_ok and coupling_ok
        )
        if split == "holdout":
            holdout_passes.append(stratum_passes)
            witnessed_paired_difference = (
                paired_different_rate is not None
                and paired_different_rate
                > thresholds.max_paired_different_rate
            )
            if witnessed_paired_difference:
                hard_failures = True
            if enough_samples and (
                not telemetry_ok or not distribution_ok or not coupling_ok
            ):
                hard_failures = True
        strata.append(
            {
                "split": split,
                "task_class": task_class,
                "final_result_class": result_class,
                "baseline_samples": len(baseline),
                "candidate_samples": len(candidate),
                "js_divergence_bits": report.js_divergence_bits,
                "total_variation": report.total_variation,
                "baseline_telemetry_loss_rate": baseline_loss,
                "candidate_telemetry_loss_rate": candidate_loss,
                "enough_samples": enough_samples,
                "telemetry_ok": telemetry_ok,
                "distribution_ok": distribution_ok,
                "paired_samples": paired_count,
                "incomplete_pair_count": incomplete_pair_count,
                "paired_different_rate": paired_different_rate,
                "paired_indeterminate_rate": paired_indeterminate_rate,
                "coupling_ok": coupling_ok,
                "passes": stratum_passes,
            }
        )

    has_calibration = any(item[0] == "calibration" for item in groups)
    has_holdout = any(item[0] == "holdout" for item in groups)
    if not has_calibration:
        eligibility_reasons.append("missing_calibration_split")
    if not has_holdout:
        eligibility_reasons.append("missing_holdout_split")

    eligible = not eligibility_reasons
    gate_passes = eligible and bool(holdout_passes) and all(holdout_passes)
    if gate_passes:
        verdict = HistoryGateVerdict.PASS
    elif hard_failures:
        verdict = HistoryGateVerdict.FAIL
    else:
        verdict = HistoryGateVerdict.HOLD
    return {
        "schema": "uar.semantic-history-review.v1",
        "evidence_plane": (
            "observed_operational" if eligible else "probability_or_ineligible"
        ),
        "eligible_for_release_gate": eligible,
        "attestation_valid": attestation_valid,
        "eligibility_reasons": sorted(set(eligibility_reasons)),
        "gate_passes": gate_passes,
        "verdict": verdict.value,
        "thresholds": asdict(thresholds),
        "run_count": len(runs),
        "duplicate_run_ids": sorted(set(duplicate_ids)),
        "integrity_issues": integrity_issues,
        "strata": strata,
    }


__all__ = [
    "CORPUS_SCHEMA",
    "ELIGIBLE_SOURCE_KIND",
    "HistoryGateThresholds",
    "HistoryGateVerdict",
    "review_semantic_history",
]
