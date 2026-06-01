"""Calibration Intelligence (Ω-6b).

Measures whether predicted confidence matches actual resolution rates.
Provides reliability buckets and calibration error metrics.
"""

from typing import Any, Dict, List


def compute_calibration(
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
    bucket_size: float = 0.1,
    min_bucket_samples: int = 1,
) -> Dict[str, Any]:
    """Compute calibration metrics from outcomes and metadata.

    Args:
        outcomes: List of outcome records from the store.
        metadata: List of metadata records with confidence values.
        bucket_size: Width of each confidence bucket (default 0.1).
        min_bucket_samples: Minimum samples for a bucket to be reported.

    Returns:
        {
            "overall_calibration_error": float,
            "mean_predicted_confidence": float,
            "mean_actual_resolution_rate": float,
            "sample_size": int,
            "reliability_buckets": [
                {
                    "bucket": "0.80-0.90",
                    "predicted_avg": float,
                    "actual_rate": float,
                    "sample_size": int,
                    "calibration_error": float,
                }
            ]
        }
    """
    # Build rec_id -> {confidence, resolved} mapping
    rec_meta: Dict[str, Dict[str, Any]] = {}
    for m in metadata:
        rid = m.get("recommendation_id")
        conf = m.get("confidence")
        if rid is not None and conf is not None:
            rec_meta[rid] = {
                "confidence": float(conf),
                "resolved": False,
                "has_outcome": False,
            }

    # Attach outcomes
    for o in outcomes:
        rid = o.get("recommendation_id")
        out_type = o.get("outcome_type")
        if rid not in rec_meta:
            continue
        if out_type == "resolved":
            rec_meta[rid]["resolved"] = True
            rec_meta[rid]["has_outcome"] = True
        elif out_type == "recurred":
            rec_meta[rid]["resolved"] = False
            rec_meta[rid]["has_outcome"] = True
        # "unknown" outcomes do not contribute to calibration

    # Filter to recommendations with both confidence and outcome
    scored = [
        rec_meta[rid]
        for rid in rec_meta
        if rec_meta[rid]["has_outcome"]
    ]

    if not scored:
        return {
            "overall_calibration_error": 0.0,
            "mean_predicted_confidence": 0.0,
            "mean_actual_resolution_rate": 0.0,
            "sample_size": 0,
            "reliability_buckets": [],
        }

    total_predicted = sum(s["confidence"] for s in scored)
    total_actual = sum(1.0 for s in scored if s["resolved"])
    n = len(scored)
    mean_pred = round(total_predicted / n, 2)
    mean_actual = round(total_actual / n, 2)
    overall_error = round(mean_pred - mean_actual, 2)

    # Build reliability buckets
    buckets: Dict[str, Dict[str, Any]] = {}
    step = int(1 / bucket_size)
    for i in range(step):
        low = i * bucket_size
        high = (i + 1) * bucket_size
        label = f"{low:.2f}-{high:.2f}"
        buckets[label] = {
            "predicted_sum": 0.0,
            "actual_sum": 0.0,
            "count": 0,
        }

    for s in scored:
        conf = s["confidence"]
        idx = min(int(conf / bucket_size), step - 1)
        low = idx * bucket_size
        high = (idx + 1) * bucket_size
        label = f"{low:.2f}-{high:.2f}"
        buckets[label]["predicted_sum"] += conf
        buckets[label]["actual_sum"] += 1.0 if s["resolved"] else 0.0
        buckets[label]["count"] += 1

    reliability_buckets: List[Dict[str, Any]] = []
    for label in sorted(buckets.keys()):
        b = buckets[label]
        count = b["count"]
        if count < min_bucket_samples:
            continue
        pred_avg = round(b["predicted_sum"] / count, 2)
        actual_rate = round(b["actual_sum"] / count, 2)
        error = round(pred_avg - actual_rate, 2)
        reliability_buckets.append(
            {
                "bucket": label,
                "predicted_avg": pred_avg,
                "actual_rate": actual_rate,
                "sample_size": count,
                "calibration_error": error,
            }
        )

    return {
        "overall_calibration_error": overall_error,
        "mean_predicted_confidence": mean_pred,
        "mean_actual_resolution_rate": mean_actual,
        "sample_size": n,
        "reliability_buckets": reliability_buckets,
    }
