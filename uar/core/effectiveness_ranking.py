"""Outcome Intelligence — Effectiveness Ranking.

Omega-6a: Computes recommendation effectiveness rankings with
Bayesian smoothing, time decay, and drift detection.
"""

import math
import time
from typing import Any, Dict, List


def _decay_weight(recorded_at: float, half_life_days: float = 30.0) -> float:
    """Exponential decay weight based on age."""
    if half_life_days <= 0:
        return 1.0
    age_days = (time.time() - recorded_at) / 86400.0
    return math.exp(-0.6931471805599453 * age_days / half_life_days)


def compute_effectiveness(
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
    min_samples: int = 5,
    half_life_days: float = 30.0,
    recent_window_days: float = 30.0,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> Dict[str, Any]:
    """Compute effectiveness rankings per recommendation category.

    Args:
        outcomes: List of outcome records from the store.
        metadata: List of metadata records mapping rec_id to category.
        min_samples: Minimum outcomes before a type is ranked.
        half_life_days: Exponential decay half-life for weighted stats.
        recent_window_days: Window for "recent" vs "historical" drift.
        alpha, beta: Bayesian smoothing prior (Laplace smoothing).

    Returns:
        {
            "generated_at": float,
            "recommendation_types": [
                {
                    "type": str,
                    "sample_size": int,
                    "resolution_rate": float,
                    "weighted_resolution_rate": float,
                    "resolved_count": int,
                    "recurred_count": int,
                    "historical_resolution_rate": float,
                    "recent_resolution_rate": float,
                    "drift": float,
                }
            ]
        }
    """
    # Build rec_id → category mapping
    rec_to_category: Dict[str, str] = {}
    for m in metadata:
        rid = m.get("recommendation_id")
        cat = m.get("category")
        if rid and cat:
            rec_to_category[rid] = cat

    # Collect per-category stats
    from collections import defaultdict

    cat_stats: Dict[str, dict] = defaultdict(
        lambda: {
            "resolved": 0,
            "recurred": 0,
            "weighted_resolved": 0.0,
            "weighted_total": 0.0,
            "recent_resolved": 0,
            "recent_total": 0,
            "historical_resolved": 0,
            "historical_total": 0,
        }
    )

    now = time.time()
    recent_cutoff = now - recent_window_days * 86400.0

    for o in outcomes:
        rid = o.get("recommendation_id")
        out_type = o.get("outcome_type")
        recorded_at = o.get("recorded_at", now)
        if not rid or not out_type or rid not in rec_to_category:
            continue

        cat = rec_to_category[rid]
        stats = cat_stats[cat]
        weight = _decay_weight(recorded_at, half_life_days)

        is_recent = recorded_at >= recent_cutoff

        if out_type == "resolved":
            stats["resolved"] += 1
            stats["weighted_resolved"] += weight
            stats["weighted_total"] += weight
            if is_recent:
                stats["recent_resolved"] += 1
                stats["recent_total"] += 1
            else:
                stats["historical_resolved"] += 1
                stats["historical_total"] += 1
        elif out_type == "recurred":
            stats["recurred"] += 1
            stats["weighted_total"] += weight
            if is_recent:
                stats["recent_total"] += 1
            else:
                stats["historical_total"] += 1
        # "unknown" is ignored for resolution rate

    # Build result list
    types: List[Dict[str, Any]] = []
    for cat, s in cat_stats.items():
        total = s["resolved"] + s["recurred"]
        if total < min_samples:
            continue

        # Raw resolution rate
        resolution_rate = round(s["resolved"] / total, 2) if total else 0.0

        # Bayesian-smoothed rate
        smoothed_rate = round(
            (s["resolved"] + alpha) / (total + alpha + beta), 2
        )

        # Weighted resolution rate
        weighted_total = s["weighted_total"]
        weighted_rate = (
            round(s["weighted_resolved"] / weighted_total, 2)
            if weighted_total
            else 0.0
        )

        # Historical vs recent drift
        hist_total = s["historical_total"]
        hist_rate = (
            round(s["historical_resolved"] / hist_total, 2)
            if hist_total
            else 0.0
        )

        recent_total = s["recent_total"]
        recent_rate = (
            round(s["recent_resolved"] / recent_total, 2)
            if recent_total
            else 0.0
        )

        drift = round(recent_rate - hist_rate, 2) if hist_total else 0.0

        types.append(
            {
                "type": cat,
                "sample_size": total,
                "resolved_count": s["resolved"],
                "recurred_count": s["recurred"],
                "resolution_rate": resolution_rate,
                "smoothed_resolution_rate": smoothed_rate,
                "weighted_resolution_rate": weighted_rate,
                "historical_resolution_rate": hist_rate,
                "recent_resolution_rate": recent_rate,
                "drift": drift,
            }
        )

    # Sort by weighted resolution rate descending
    types.sort(key=lambda x: x["weighted_resolution_rate"], reverse=True)

    return {
        "generated_at": now,
        "recommendation_types": types,
    }
