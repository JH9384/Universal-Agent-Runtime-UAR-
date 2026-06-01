"""Replay Intelligence — Evidence Linkage (Ω-6c).

Links recommendations to outcomes and the runs that produced them,
forming the foundation of an operational knowledge graph.
"""

from typing import Any, Dict, List, Optional


def get_evidence(
    recommendation_id: str,
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Retrieve evidence for a single recommendation.

    Args:
        recommendation_id: The recommendation to look up.
        outcomes: All outcome records.
        metadata: All metadata records.

    Returns:
        Evidence record or None if not found.
    """
    meta = next(
        (
            m for m in metadata
            if m.get("recommendation_id") == recommendation_id
        ),
        None,
    )
    if meta is None:
        return None

    rec_outcomes = [
        o for o in outcomes
        if o.get("recommendation_id") == recommendation_id
    ]

    # Use the most recent outcome
    latest = None
    for o in rec_outcomes:
        if latest is None or o.get("recorded_at", 0) > latest.get(
            "recorded_at", 0
        ):
            latest = o

    return {
        "recommendation_id": recommendation_id,
        "category": meta.get("category"),
        "source": meta.get("source"),
        "title": meta.get("title"),
        "confidence": meta.get("confidence"),
        "run_id": meta.get("run_id"),
        "outcome": latest.get("outcome_type") if latest else None,
        "outcome_recorded_at": latest.get("recorded_at") if latest else None,
    }


def aggregate_evidence(
    outcomes: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
    min_samples: int = 1,
) -> Dict[str, Any]:
    """Aggregate evidence by recommendation type.

    Returns:
        {
            "recommendation_types": [
                {
                    "type": str,
                    "resolution_rate": float,
                    "sample_size": int,
                    "supporting_replays": int,
                }
            ]
        }
    """
    from collections import defaultdict

    type_stats: Dict[str, dict] = defaultdict(
        lambda: {
            "resolved": 0,
            "recurred": 0,
            "run_ids": set(),
        }
    )

    # Build metadata lookup
    meta_lookup: Dict[str, Dict[str, Any]] = {
        m["recommendation_id"]: m
        for m in metadata
        if m.get("recommendation_id")
    }

    for o in outcomes:
        rid = o.get("recommendation_id")
        out_type = o.get("outcome_type")
        meta = meta_lookup.get(rid)
        if not meta:
            continue

        cat = meta.get("category")
        if not cat:
            continue

        stats = type_stats[cat]
        if out_type == "resolved":
            stats["resolved"] += 1
        elif out_type == "recurred":
            stats["recurred"] += 1

        run_id = meta.get("run_id")
        if run_id:
            stats["run_ids"].add(run_id)

    types: List[Dict[str, Any]] = []
    for cat, s in type_stats.items():
        total = s["resolved"] + s["recurred"]
        if total < min_samples:
            continue

        rate = round(s["resolved"] / total, 2) if total else 0.0
        types.append(
            {
                "type": cat,
                "resolution_rate": rate,
                "sample_size": total,
                "supporting_replays": len(s["run_ids"]),
            }
        )

    # Sort by resolution rate descending
    types.sort(key=lambda x: x["resolution_rate"], reverse=True)

    return {"recommendation_types": types}
