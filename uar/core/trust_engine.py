"""Adaptive Trust Engine (Ω-7a).

Composes effectiveness, calibration, evidence, and drift into a
single trust score per recommendation type.
"""

import time
from typing import Any, Dict, List

from uar.core.calibration import compute_calibration
from uar.core.effectiveness_ranking import compute_effectiveness
from uar.core.evidence import aggregate_evidence


def compute_trust(
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute trust scores for each recommendation type.

    Trust formula:
        trust = (effectiveness + calibration + evidence) / 3 - drift_penalty

    All values clamped to [0, 1].

    Returns:
        {
            "generated_at": float,
            "system_calibration_error": float,
            "recommendation_types": [
                {
                    "type": str,
                    "trust_score": float,
                    "effectiveness_component": float,
                    "calibration_component": float,
                    "evidence_component": float,
                    "drift_penalty": float,
                }
            ]
        }
    """
    eff_result = compute_effectiveness(outcomes, metadata)
    cal_result = compute_calibration(outcomes, metadata)
    evi_result = aggregate_evidence(outcomes, metadata)

    eff_by_type = {
        t["type"]: t for t in eff_result["recommendation_types"]
    }
    evi_by_type = {
        t["type"]: t for t in evi_result["recommendation_types"]
    }

    cal_error = cal_result["overall_calibration_error"]
    calibration_component = max(0.0, 1.0 - abs(cal_error))

    trust_types: List[Dict[str, Any]] = []
    for type_name, eff_data in eff_by_type.items():
        eff = eff_data.get(
            "weighted_resolution_rate",
            eff_data.get("resolution_rate", 0.0),
        )

        evi_data = evi_by_type.get(type_name, {})
        sample_size = evi_data.get("sample_size", 0)
        replays = evi_data.get("supporting_replays", 0)
        evidence_component = min(
            1.0, (sample_size / 50.0 + replays / 20.0) / 2
        )

        drift = eff_data.get("drift", 0.0)
        drift_penalty = max(0.0, -drift)

        trust = (eff + calibration_component + evidence_component) / 3.0
        trust -= drift_penalty
        trust = max(0.0, min(1.0, trust))

        trust_types.append(
            {
                "type": type_name,
                "trust_score": round(trust, 2),
                "effectiveness_component": round(eff, 2),
                "calibration_component": round(
                    calibration_component, 2
                ),
                "evidence_component": round(evidence_component, 2),
                "drift_penalty": round(drift_penalty, 2),
            }
        )

    trust_types.sort(key=lambda x: x["trust_score"], reverse=True)

    return {
        "generated_at": time.time(),
        "system_calibration_error": cal_error,
        "recommendation_types": trust_types,
    }
