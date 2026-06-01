"""Adaptive confidence computation for Ω-5.4.

Uses operator feedback (accept / reject / dismiss) to compute a modifier
applied to the base recommendation confidence.

Formula:
    adaptive_confidence = base_confidence * operator_modifier

Modifier rules (conservative, evidence-gated):
    shown_count >= 10                → adaptation eligible
    acceptance_rate > 0.80          → modifier += 0.05
    acceptance_rate > 0.90          → modifier += 0.10  (cumulative)
    rejection_rate  > 0.60          → modifier -= 0.10
    dismissal_rate  > 0.70          → modifier -= 0.05
    0.5 <= modifier <= 1.5         → clamp

No persistent state required — the modifier is recomputed from live
store feedback each time recommendations are generated. This prevents
feedback traps because the modifier always reflects actual operator
behavior, not cached or decayed values.
"""

from __future__ import annotations

from typing import Any, Dict


# Minimum shown events before modifier deviates from 1.0
MIN_SHOWN_THRESHOLD = 10

# Modifier adjustment steps
_ACCEPT_80_BUMP = 0.05
_ACCEPT_90_BUMP = 0.10
_REJECT_60_PENALTY = 0.10
_DISMISS_70_PENALTY = 0.05

# Clamp bounds
_MODIFIER_MIN = 0.5
_MODIFIER_MAX = 1.5


def compute_modifier(
    shown_count: int,
    accepted_count: int,
    rejected_count: int,
    dismissed_count: int,
) -> float:
    """Compute the operator_modifier from feedback counts.

    Returns 1.0 when insufficient evidence exists.
    """
    if shown_count < MIN_SHOWN_THRESHOLD:
        return 1.0

    acceptance_rate = accepted_count / shown_count
    rejection_rate = rejected_count / shown_count
    dismissal_rate = dismissed_count / shown_count

    modifier = 1.0

    if acceptance_rate > 0.90:
        modifier += _ACCEPT_90_BUMP
    elif acceptance_rate > 0.80:
        modifier += _ACCEPT_80_BUMP

    if rejection_rate > 0.60:
        modifier -= _REJECT_60_PENALTY

    if dismissal_rate > 0.70:
        modifier -= _DISMISS_70_PENALTY

    return max(_MODIFIER_MIN, min(_MODIFIER_MAX, modifier))


def compute_adaptive_confidence(
    base_confidence: float,
    shown_count: int,
    accepted_count: int,
    rejected_count: int,
    dismissed_count: int,
) -> float:
    """Return the adaptive confidence value.

    If evidence is insufficient, returns the base confidence unchanged.
    """
    modifier = compute_modifier(
        shown_count, accepted_count, rejected_count, dismissed_count
    )
    return base_confidence * modifier


def build_quality_stats(
    shown: list[dict],
    feedback: list[dict],
) -> dict[str, dict]:
    """Aggregate shown + feedback into per-recommendation stats.

    Returns a dict mapping recommendation_id → counts dict suitable
    for passing to compute_modifier / compute_adaptive_confidence.
    """
    stats: Dict[str, Dict[str, Any]] = {}

    for s in shown:
        rid = s.get("recommendation_id")
        if not rid:
            continue
        entry = stats.setdefault(
            rid,
            {
                "shown_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "dismissed_count": 0,
            },
        )
        entry["shown_count"] += 1

    for f in feedback:
        rid = f.get("recommendation_id")
        action = f.get("action")
        if not rid or not action:
            continue
        entry = stats.setdefault(
            rid,
            {
                "shown_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "dismissed_count": 0,
            },
        )
        if action == "accept":
            entry["accepted_count"] += 1
        elif action == "reject":
            entry["rejected_count"] += 1
        elif action == "dismiss":
            entry["dismissed_count"] += 1

    return stats
