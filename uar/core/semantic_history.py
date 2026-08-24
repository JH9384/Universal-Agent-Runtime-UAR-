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
from typing import Any

from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_statistics import compare_semantic_distributions
from uar.core.semantic_trace import (
    SEMANTIC_EVENT_TYPES,
    semantic_trace_from_events,
    validate_semantic_trace,
)

CORPUS_SCHEMA = "uar.semantic-history-corpus.v1"
ELIGIBLE_SOURCE_KIND = "observed_operational"


@dataclass(frozen=True, slots=True)
class HistoryGateThresholds:
    min_samples_per_cohort: int = 20
    max_js_divergence_bits: float = 0.02
    max_total_variation: float = 0.05
    max_telemetry_loss_rate: float = 0.01
    max_telemetry_loss_delta: float = 0.005


DEFAULT_HISTORY_GATE_THRESHOLDS = HistoryGateThresholds()


def _trace(events: Sequence[Mapping[str, Any]]):
    has_semantic_events = any(
        str(event.get("type", "")) in SEMANTIC_EVENT_TYPES
        for event in events
    )
    source = tuple(events)
    if not has_semantic_events:
        source = observe_runtime_semantics(source)
    return semantic_trace_from_events(source)


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
) -> dict[str, Any]:
    """Review an already-sanitized, pre-split runtime history corpus.

    Runs are grouped by ``split`` (``calibration`` or ``holdout``), task class,
    and final-result class.  Each stratum must contain baseline and candidate
    cohorts.  Release status is determined from the untouched holdout only;
    calibration results are reported but cannot close the gate.
    """

    eligibility_reasons = list(_corpus_eligibility(payload))
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        eligibility_reasons.append("missing_runs")
        runs = []

    groups: dict[tuple[str, str, str], dict[str, list[Any]]] = defaultdict(
        lambda: {"baseline": [], "candidate": []}
    )
    integrity_issues = []
    duplicate_ids = []
    seen_ids = set()

    for index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            integrity_issues.append({"run_index": index, "code": "run_not_object"})
            continue
        run_id = str(run.get("run_id", ""))
        if not run_id:
            integrity_issues.append({"run_index": index, "code": "missing_run_id"})
        elif run_id in seen_ids:
            duplicate_ids.append(run_id)
        seen_ids.add(run_id)

        split = str(run.get("split", ""))
        cohort = str(run.get("cohort", ""))
        task_class = str(run.get("task_class", ""))
        result_class = str(run.get("final_result_class", ""))
        if split not in {"calibration", "holdout"}:
            integrity_issues.append({"run_id": run_id, "code": "invalid_split"})
            continue
        if cohort not in {"baseline", "candidate"}:
            integrity_issues.append({"run_id": run_id, "code": "invalid_cohort"})
            continue
        if not task_class or not result_class:
            integrity_issues.append({"run_id": run_id, "code": "missing_stratum"})
            continue
        events = run.get("events")
        if not isinstance(events, list) or not events:
            integrity_issues.append({"run_id": run_id, "code": "missing_events"})
            continue

        trace = _trace(events)
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

    if duplicate_ids:
        eligibility_reasons.append("duplicate_run_ids")
    if integrity_issues:
        eligibility_reasons.append("trace_integrity_issues")

    strata = []
    holdout_passes = []
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
        stratum_passes = enough_samples and telemetry_ok and distribution_ok
        if split == "holdout":
            holdout_passes.append(stratum_passes)
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
    return {
        "schema": "uar.semantic-history-review.v1",
        "evidence_plane": (
            "observed_operational" if eligible else "probability_or_ineligible"
        ),
        "eligible_for_release_gate": eligible,
        "eligibility_reasons": sorted(set(eligibility_reasons)),
        "gate_passes": gate_passes,
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
    "review_semantic_history",
]
