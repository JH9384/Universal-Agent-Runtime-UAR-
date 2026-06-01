"""Replay confidence scoring for UAR run records.

Replay Confidence is the first measurable trust primitive in the Trust Spine.
It converts replay/reconstruction evidence into a score, tier, and warning set
that can be consumed by Certification, Mission Control, and Replay Explorer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from uar.core.contracts import RunRecord
from uar.core.exceptions import EventContractError
from uar.core.replay import validate_event_stream
from uar.core.timeline import timeline_from_record


@dataclass(slots=True)
class ReplayConfidenceWarning:
    """A warning generated while scoring replay confidence."""

    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class ReplayConfidenceReport:
    """Replay confidence score and evidence breakdown."""

    run_id: str
    score: int
    tier: str
    dimensions: Dict[str, int]
    warnings: List[ReplayConfidenceWarning] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-serializable report representation."""
        return {
            "run_id": self.run_id,
            "confidence": {
                "score": self.score,
                "tier": self.tier,
                "warnings": [asdict(w) for w in self.warnings],
                "errors": list(self.errors),
                "dimensions": dict(self.dimensions),
            },
        }


def confidence_tier(score: int) -> str:
    """Map confidence score to operator-facing tier."""
    if score >= 95:
        return "Verified"
    if score >= 85:
        return "High"
    if score >= 70:
        return "Medium"
    if score >= 50:
        return "Low"
    return "Failed"


def _score_event_completeness(
    record: RunRecord,
    warnings: List[ReplayConfidenceWarning],
    errors: List[str],
) -> int:
    events = list(record.events or [])
    if not events:
        errors.append("Cannot score replay confidence without events")
        warnings.append(ReplayConfidenceWarning(
            "missing_events",
            "Run record contains no events",
            "error",
        ))
        return 0

    canonical = all("schema_version" in ev for ev in events)
    if not canonical:
        warnings.append(ReplayConfidenceWarning(
            "legacy_event_shape",
            "One or more events do not use canonical "
            "RuntimeEvent schema",
        ))
        # Legacy events may still support partial operator understanding.
        return 60

    try:
        validate_event_stream(events)
        return 100
    except EventContractError as exc:
        errors.append(str(exc))
        warnings.append(ReplayConfidenceWarning(
            "invalid_event_schema", str(exc), "error"
        ))
        return 40


def _score_timeline_completeness(
    record: RunRecord,
    warnings: List[ReplayConfidenceWarning],
) -> int:
    try:
        timeline = timeline_from_record(record)
    except Exception as exc:  # pragma: no cover - defensive guard
        warnings.append(ReplayConfidenceWarning(
            "timeline_gap",
            f"Timeline projection failed: {exc}",
            "error",
        ))
        return 0

    summary = timeline.get("summary", {})
    event_types = timeline.get("event_types", [])
    if not event_types:
        warnings.append(ReplayConfidenceWarning(
            "timeline_gap", "Timeline has no event types"
        ))
        return 40

    score = 100
    if summary.get("status") in {None, "unknown"}:
        warnings.append(ReplayConfidenceWarning(
            "timeline_gap", "Timeline status is unknown"
        ))
        score -= 20
    if record.skills and not timeline.get("skills"):
        warnings.append(ReplayConfidenceWarning(
            "timeline_gap", "Timeline has no projected skills"
        ))
        score -= 15
    return max(0, score)


def _score_store_consistency(
    record: RunRecord,
    warnings: List[ReplayConfidenceWarning],
) -> int:
    score = 100
    run_id_missing = not record.run_id
    goal_id_missing = not record.goal_id

    if run_id_missing:
        warnings.append(ReplayConfidenceWarning(
            "store_record_missing",
            "Run record missing run_id",
            "error",
        ))
        score -= 50
    if goal_id_missing:
        warnings.append(ReplayConfidenceWarning(
            "store_record_missing",
            "Run record missing goal_id",
            "error",
        ))
        score -= 30
    if record.events:
        run_id_mismatch_seen = False
        goal_id_mismatch_seen = False
        for ev in record.events:
            # Only flag mismatch when the record field is present; absence is
            # already penalised above and the two deductions must not stack.
            ev_run_id = ev.get("run_id")
            ev_goal_id = ev.get("goal_id")
            if (
                not run_id_missing
                and not run_id_mismatch_seen
                and ev_run_id is not None
                and ev_run_id != ""
                and str(ev_run_id) != record.run_id
            ):
                warnings.append(ReplayConfidenceWarning(
                    "store_event_mismatch",
                    "Event run_id does not match "
                    "RunRecord.run_id",
                    "error",
                ))
                score -= 40
                run_id_mismatch_seen = True
            if (
                not goal_id_missing
                and not goal_id_mismatch_seen
                and ev_goal_id is not None
                and ev_goal_id != ""
                and str(ev_goal_id) != record.goal_id
            ):
                warnings.append(ReplayConfidenceWarning(
                    "store_event_mismatch",
                    "Event goal_id does not match "
                    "RunRecord.goal_id",
                    "error",
                ))
                score -= 30
                goal_id_mismatch_seen = True
            if run_id_mismatch_seen and goal_id_mismatch_seen:
                break
    return max(0, score)


def _score_reconstruction(
    record: RunRecord,
    warnings: List[ReplayConfidenceWarning],
) -> int:
    events = list(record.events or [])
    if not events:
        return 0
    if not all("schema_version" in ev for ev in events):
        warnings.append(ReplayConfidenceWarning(
            "partial_replay",
            "Legacy events allow partial but not strict "
            "reconstruction",
        ))
        return 60
    try:
        validate_event_stream(events)
        return 100
    except EventContractError as exc:
        warnings.append(ReplayConfidenceWarning(
            "reconstruction_failed", str(exc), "error"
        ))
        return 30


def _score_artifact_completeness(
    record: RunRecord,
    warnings: List[ReplayConfidenceWarning],
) -> int:
    # v1 treats outputs/final_context/UOR provenance as artifact hints.
    has_outputs = bool(record.outputs)
    has_context = bool(record.final_context)
    has_uor = bool(record.uor_address or record.uor_witness)
    if has_outputs and (has_context or has_uor):
        return 100
    if has_outputs:
        return 90
    if has_context or has_uor:
        return 75
    warnings.append(ReplayConfidenceWarning(
        "artifact_missing",
        "No outputs, final context, or UOR provenance found",
        "warning",
    ))
    return 0


def score_replay(record: RunRecord) -> ReplayConfidenceReport:
    """Score replay confidence for a run record.

    The scoring model follows docs/REPLAY_CONFIDENCE.md.
    """
    warnings: List[ReplayConfidenceWarning] = []
    errors: List[str] = []

    dimensions = {
        "event_completeness": _score_event_completeness(
            record, warnings, errors
        ),
        "timeline_completeness": _score_timeline_completeness(
            record, warnings
        ),
        "store_consistency": _score_store_consistency(
            record, warnings
        ),
        "replay_reconstruction_success": _score_reconstruction(
            record, warnings
        ),
        "artifact_completeness": _score_artifact_completeness(
            record, warnings
        ),
    }

    weighted = (
        dimensions["event_completeness"] * 0.30
        + dimensions["timeline_completeness"] * 0.20
        + dimensions["store_consistency"] * 0.20
        + dimensions["replay_reconstruction_success"] * 0.20
        + dimensions["artifact_completeness"] * 0.10
    )
    score = int(round(max(0.0, min(100.0, weighted))))
    return ReplayConfidenceReport(
        run_id=record.run_id,
        score=score,
        tier=confidence_tier(score),
        dimensions=dimensions,
        warnings=warnings,
        errors=errors,
    )


__all__ = [
    "ReplayConfidenceReport",
    "ReplayConfidenceWarning",
    "confidence_tier",
    "score_replay",
]
