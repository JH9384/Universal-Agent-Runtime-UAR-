from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FailureClassification:
    category: str
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "reasons": self.reasons,
            "details": self.details,
        }


def classify_failure(result=None, evaluation=None) -> FailureClassification:
    if result is None:
        return FailureClassification("missing_result", ["no_result_returned"])

    status = getattr(result, "status", None)
    outputs = getattr(result, "outputs", []) or []
    errors = getattr(result, "errors", []) or []
    evaluation_dict = evaluation.to_dict() if hasattr(evaluation, "to_dict") else (evaluation or {})
    eval_reasons = evaluation_dict.get("reasons", []) if isinstance(evaluation_dict, dict) else []
    eval_score = evaluation_dict.get("score") if isinstance(evaluation_dict, dict) else None

    details = {
        "status": status,
        "output_count": len(outputs),
        "error_count": len(errors),
        "evaluation_score": eval_score,
    }

    if errors:
        joined = "\n".join(str(error).lower() for error in errors)
        if "timed out" in joined or "timeout" in joined:
            return FailureClassification("timeout", ["skill_timeout"], details)
        if "not found" in joined or "keyerror" in joined:
            return FailureClassification("invalid_skill_or_input", ["missing_skill_or_input"], details)
        return FailureClassification("runtime_error", ["errors_present"], details)

    if status != "completed":
        return FailureClassification("incomplete_run", ["status_not_completed"], details)

    if not outputs:
        return FailureClassification("no_output", ["outputs_missing"], details)

    if "output_thin" in eval_reasons:
        return FailureClassification("low_quality_output", ["output_thin"], details)

    if "goal_terms_not_reflected" in eval_reasons:
        return FailureClassification("goal_mismatch", ["goal_terms_not_reflected"], details)

    if eval_score is not None and eval_score < 0.70:
        return FailureClassification("low_evaluation_score", ["score_below_threshold"], details)

    return FailureClassification("none", [], details)
