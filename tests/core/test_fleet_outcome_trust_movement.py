"""D4C-S1.5 regression: fleet-linked outcomes move existing trust.

This test intentionally uses the existing trust engine and recommendation
metadata records.  It does not introduce a fleet-specific outcome table or a
second fleet trust score.
"""

import time

from uar.core.fleet_signals import build_fleet_signals, build_fleet_summary
from uar.core.trust_engine import compute_trust


def _type_score(trust_result, type_name):
    for item in trust_result["recommendation_types"]:
        if item["type"] == type_name:
            return item
    return None


def test_fleet_linked_recommendation_outcomes_move_existing_trust_score():
    now = time.time()
    records = [
        {
            "run_id": "fleet-r1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {
                "service": "svc-a",
                "recommendation_id": "rec-fleet-1",
            },
            "created_at": now,
        }
    ]
    fleet_summary = build_fleet_summary(build_fleet_signals(records))
    top = fleet_summary["top_signal"]

    assert top["linked_recommendation_ids"] == ["rec-fleet-1"]

    metadata = [
        {
            "recommendation_id": "rec-fleet-1",
            "category": "fleet_recovery",
            "source": "fleet_signal",
            "title": "Recover svc-a",
            "confidence": 0.80,
            "run_id": "fleet-r1",
            "recorded_at": now,
        }
    ]

    recurred_outcomes = [
        {
            "recommendation_id": "rec-fleet-1",
            "outcome_type": "recurred",
            "recorded_at": now,
        }
        for _ in range(5)
    ]
    resolved_outcomes = [
        {
            "recommendation_id": "rec-fleet-1",
            "outcome_type": "resolved",
            "recorded_at": now,
        }
        for _ in range(5)
    ]

    low_trust = compute_trust(recurred_outcomes, metadata)
    high_trust = compute_trust(resolved_outcomes, metadata)

    low = _type_score(low_trust, "fleet_recovery")
    high = _type_score(high_trust, "fleet_recovery")

    assert low is not None
    assert high is not None
    assert high["trust_score"] > low["trust_score"]
    assert high["effectiveness_component"] > low["effectiveness_component"]


def test_fleet_outcome_trust_uses_existing_metadata_category_not_signal_id():
    now = time.time()
    outcomes = [
        {
            "recommendation_id": "rec-fleet-2",
            "outcome_type": "resolved",
            "recorded_at": now,
        }
        for _ in range(5)
    ]
    metadata = [
        {
            "recommendation_id": "rec-fleet-2",
            "category": "cache_recovery",
            "source": "fleet_signal",
            "title": "Recover cache segment",
            "confidence": 0.75,
            "run_id": "fleet-r2",
        }
    ]

    trust = compute_trust(outcomes, metadata)
    assert _type_score(trust, "cache_recovery") is not None
    assert _type_score(trust, "fleet:service:svc-a") is None
