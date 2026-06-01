"""Trust-weighted recommendation ranking (Ω-7b).

Soft-blends confidence and trust for recommendation ordering.
Operates behind the ENABLE_TRUST_RANKING feature flag.
"""

from __future__ import annotations

from typing import Any, Dict, List

from uar.core.operational_learning import Recommendation


# Ω-7b Stage 3: Soft blend weights.
# Weighted sum is gentler than multiplication for initial rollout.
_CONFIDENCE_WEIGHT = 0.7
_TRUST_WEIGHT = 0.3


def compute_blend(confidence: float, trust: float) -> float:
    """Compute a soft-blended rank score.

    Returns: 0.7 * confidence + 0.3 * trust
    Both inputs are expected to be in [0, 1].
    Output is clamped to [0, 1].
    """
    score = _CONFIDENCE_WEIGHT * confidence + _TRUST_WEIGHT * trust
    return max(0.0, min(1.0, score))


def attach_trust_to_recommendations(
    recommendations: List[Recommendation],
    trust_result: Dict[str, Any],
) -> None:
    """Attach trust_score to each recommendation from trust_result.

    trust_result is the output of compute_trust().  Maps trust by
    recommendation type (category).  Each rec gets the trust_score
    for its category, defaulting to 0.0 when unknown.
    """
    trust_by_type: Dict[str, float] = {}
    for t in trust_result.get("recommendation_types", []):
        type_name = t.get("type", "")
        if type_name:
            trust_by_type[type_name] = t.get("trust_score", 0.0)

    for rec in recommendations:
        rec.trust_score = trust_by_type.get(rec.category, 0.0)


def sort_by_blend(
    recommendations: List[Recommendation],
) -> None:
    """In-place sort by priority then blended score descending.

    Uses the soft blend formula.  Critical priority still wins over
    blended score within the same priority band.

    The original rec.confidence is preserved; a temporary _blend_score
    attribute is used for ordering so calibration metadata remains
    uncorrupted.
    """
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    for rec in recommendations:
        rec._blend_score = compute_blend(  # type: ignore[attr-defined]
            rec.confidence, rec.trust_score
        )

    recommendations.sort(
        key=lambda r: (
            priority_order.get(r.priority, 4),
            -r._blend_score,  # type: ignore[attr-defined]
        )
    )
