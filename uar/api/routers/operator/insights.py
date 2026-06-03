"""Insight Generation router (Phase F)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _load_all_incidents,
    _load_all_investigations,
    _load_all_snapshots,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/insights/patterns")
async def get_incident_patterns(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Discover recurring patterns in incidents."""
    auth_middleware(credentials)

    def _analyze():
        incidents = _load_all_incidents()
        if not incidents:
            return {"patterns": [], "narrative": "No incidents to analyze."}

        severity_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        title_words: Dict[str, int] = {}
        linked_run_counts: Dict[str, int] = {}
        resolution_times: List[int] = []

        for inc in incidents:
            sev = inc.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            st = inc.get("status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1

            title = inc.get("title", "").lower()
            for word in title.split():
                if len(word) > 3:
                    title_words[word] = title_words.get(word, 0) + 1

            for rid in inc.get("linked_run_ids", []):
                linked_run_counts[rid] = linked_run_counts.get(rid, 0) + 1

            created = inc.get("created_at", 0)
            updated = inc.get("updated_at", created)
            if inc.get("status") == "resolved" and updated > created:
                resolution_times.append(updated - created)

        recurring_words = sorted(
            [
                {"word": w, "count": c}
                for w, c in title_words.items() if c >= 2
            ],
            key=lambda x: -x["count"],
        )[:10]

        hot_runs = sorted(
            [
                {"run_id": r, "incident_count": c}
                for r, c in linked_run_counts.items()
                if c >= 2
            ],
            key=lambda x: -x["incident_count"],
        )[:5]

        avg_resolution = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times
            else None
        )

        narrative_parts = ["Incident Pattern Analysis"]
        if recurring_words:
            themes = ", ".join(w["word"] for w in recurring_words[:3])
            narrative_parts.append(f"Recurring themes: {themes}.")
        if hot_runs:
            narrative_parts.append(
                f"{len(hot_runs)} run(s) linked to multiple incidents."
            )
        if avg_resolution is not None:
            narrative_parts.append(
                f"Average resolution time: {avg_resolution / 3600:.1f}h."
            )

        return {
            "pattern_type": "incident_patterns",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "total_incidents": len(incidents),
            "severity_distribution": severity_counts,
            "status_distribution": status_counts,
            "recurring_themes": recurring_words,
            "hot_runs": hot_runs,
            "avg_resolution_seconds": avg_resolution,
        }

    return await run_in_threadpool(_analyze)


@router.get("/api/uar/insights/evolution")
async def get_recommendation_evolution(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Track how recommendation trust evolves over time."""
    auth_middleware(credentials)

    def _analyze():
        snapshots = _load_all_snapshots(limit=50)
        if not snapshots:
            return {
                "trajectories": [],
                "narrative": "No snapshots for evolution analysis.",
            }

        trajectories: Dict[str, List[Dict[str, Any]]] = {}
        for snap in sorted(snapshots, key=lambda x: x.get("timestamp", 0)):
            ts = snap.get("timestamp", 0)
            trust = snap.get("trust", {})
            for t in trust.get("recommendation_types", []):
                cat = t.get("type", "")
                if cat:
                    if cat not in trajectories:
                        trajectories[cat] = []
                    trajectories[cat].append(
                        {
                            "timestamp": ts,
                            "trust_score": t.get("trust_score"),
                            "drift_penalty": t.get("drift_penalty"),
                        }
                    )

        velocities: List[Dict[str, Any]] = []
        for cat, points in trajectories.items():
            if len(points) >= 2:
                first = points[0]["trust_score"] or 0
                last = points[-1]["trust_score"] or 0
                delta = last - first
                velocities.append(
                    {
                        "type": cat,
                        "start_trust": first,
                        "end_trust": last,
                        "delta": round(delta, 3),
                        "direction": (
                            "improving"
                            if delta > 0.05
                            else "declining"
                            if delta < -0.05
                            else "stable"
                        ),
                        "snapshot_count": len(points),
                    }
                )

        velocities.sort(key=lambda x: -abs(x["delta"]))

        narrative_parts = ["Recommendation Evolution"]
        improving = [v for v in velocities if v["direction"] == "improving"]
        declining = [v for v in velocities if v["direction"] == "declining"]
        if improving:
            narrative_parts.append(f"{len(improving)} type(s) improving.")
        if declining:
            narrative_parts.append(f"{len(declining)} type(s) declining.")
        if not improving and not declining:
            narrative_parts.append("Trust stable across types.")

        return {
            "insight_type": "recommendation_evolution",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "snapshot_count": len(snapshots),
            "trajectories": {
                cat: pts for cat, pts in list(trajectories.items())[:20]
            },
            "velocities": velocities[:10],
        }

    return await run_in_threadpool(_analyze)


@router.get("/api/uar/insights/workflows")
async def get_operator_workflows(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Analyze investigation workflows that lead to resolution."""
    auth_middleware(credentials)

    def _analyze():
        investigations = _load_all_investigations()
        if not investigations:
            return {
                "workflows": [],
                "narrative": "No investigations to analyze.",
            }

        resolved = [
            inv for inv in investigations if inv.get("status") == "closed"
        ]
        active = [
            inv for inv in investigations if inv.get("status") == "active"
        ]

        sequence_counts: Dict[str, int] = {}
        for inv in resolved:
            actions = inv.get("actions", [])
            seq = " -> ".join(
                a.get("type", "unknown") for a in actions
            )
            if seq:
                sequence_counts[seq] = sequence_counts.get(seq, 0) + 1

        common_sequences = sorted(
            [{"sequence": s, "count": c} for s, c in sequence_counts.items()],
            key=lambda x: -x["count"],
        )[:5]

        action_freq: Dict[str, int] = {}
        for inv in investigations:
            for a in inv.get("actions", []):
                atype = a.get("type", "unknown")
                action_freq[atype] = action_freq.get(atype, 0) + 1

        top_actions = sorted(
            [{"type": t, "count": c} for t, c in action_freq.items()],
            key=lambda x: -x["count"],
        )[:10]

        total = len(investigations)
        resolution_rate = len(resolved) / total if total > 0 else 0

        narrative_parts = ["Operator Workflow Analysis"]
        narrative_parts.append(
            f"{len(resolved)} resolved of {total} investigations."
        )
        if common_sequences:
            narrative_parts.append(
                "Most common resolution path: "
                f"{common_sequences[0]['sequence']}."
            )
        if top_actions:
            narrative_parts.append(
                f"Most frequent action: {top_actions[0]['type']}."
            )

        return {
            "insight_type": "operator_workflows",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "total_investigations": total,
            "resolved_count": len(resolved),
            "active_count": len(active),
            "resolution_rate": round(resolution_rate, 2),
            "common_sequences": common_sequences,
            "top_actions": top_actions,
        }

    return await run_in_threadpool(_analyze)


@router.get("/api/uar/insights/clusters")
async def get_knowledge_clusters(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Discover hidden clusters in operational knowledge."""
    auth_middleware(credentials)

    def _analyze():
        incidents = _load_all_incidents()
        run_to_incidents: Dict[str, List[str]] = {}
        for inc in incidents:
            for rid in inc.get("linked_run_ids", []):
                run_to_incidents.setdefault(rid, []).append(inc["id"])

        pairs: Dict[str, int] = {}
        for rid, iids in run_to_incidents.items():
            if len(iids) >= 2:
                for i in range(len(iids)):
                    for j in range(i + 1, len(iids)):
                        pair_key = f"{iids[i]}::{iids[j]}"
                        pairs[pair_key] = pairs.get(pair_key, 0) + 1

        clusters = [
            {
                "incident_a": k.split("::")[0],
                "incident_b": k.split("::")[1],
                "shared_runs": v,
            }
            for k, v in pairs.items()
        ]
        clusters.sort(key=lambda x: -x["shared_runs"])

        rec_cat_counts: Dict[str, int] = {}
        try:
            metadata = store.get_recommendation_metadata(limit=5000)
            for m in metadata:
                cat = m.get("category", "")
                if cat:
                    rec_cat_counts[cat] = rec_cat_counts.get(cat, 0) + 1
        except Exception:
            pass

        narrative_parts = ["Knowledge Cluster Analysis"]
        if clusters:
            narrative_parts.append(
                f"{len(clusters)} incident cluster(s) found."
            )
        else:
            narrative_parts.append("No incident clusters detected yet.")

        return {
            "insight_type": "knowledge_clusters",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "incident_clusters": clusters[:10],
            "recommendation_category_counts": {
                k: v
                for k, v in sorted(
                    rec_cat_counts.items(), key=lambda x: -x[1]
                )[:10]
            },
        }

    return await run_in_threadpool(_analyze)


@router.get("/api/uar/insights/operator-intelligence")
async def get_operator_intelligence(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Identify operator behaviors that consistently resolve incidents."""
    auth_middleware(credentials)

    def _analyze():
        investigations = _load_all_investigations()
        resolved = [
            inv for inv in investigations if inv.get("status") == "closed"
        ]

        if not resolved:
            return {
                "patterns": [],
                "narrative": "No resolved investigations to analyze.",
            }

        resolved_actions: Dict[str, int] = {}
        unresolved_actions: Dict[str, int] = {}

        for inv in investigations:
            target = (
                resolved_actions
                if inv.get("status") == "closed"
                else unresolved_actions
            )
            for a in inv.get("actions", []):
                atype = a.get("type", "unknown")
                target[atype] = target.get(atype, 0) + 1

        action_lift: List[Dict[str, Any]] = []
        total_resolved = len(resolved)
        total_unresolved = len(investigations) - total_resolved

        for action, res_count in resolved_actions.items():
            unres_count = unresolved_actions.get(action, 0)
            res_rate = res_count / total_resolved if total_resolved > 0 else 0
            unres_rate = (
                unres_count / total_unresolved
                if total_unresolved > 0 else 0
            )
            lift = res_rate / (unres_rate + 0.001)
            action_lift.append(
                {
                    "action": action,
                    "resolved_count": res_count,
                    "unresolved_count": unres_count,
                    "lift": round(lift, 2),
                }
            )

        action_lift.sort(key=lambda x: -x["lift"])

        time_by_first_action: Dict[str, List[int]] = {}
        for inv in resolved:
            actions = inv.get("actions", [])
            if actions:
                first = actions[0].get("type", "unknown")
                duration = (
                    inv.get("ended_at") or inv.get("updated_at", 0)
                ) - inv.get("started_at", 0)
                if duration > 0:
                    time_by_first_action.setdefault(
                        first, []
                    ).append(duration)

        avg_time = [
            {
                "first_action": a,
                "avg_seconds": round(sum(times) / len(times)),
                "count": len(times),
            }
            for a, times in time_by_first_action.items()
        ]
        avg_time.sort(key=lambda x: x["avg_seconds"])

        narrative_parts = ["Operator Intelligence"]
        if action_lift:
            narrative_parts.append(
                f"Strongest resolution signal: {action_lift[0]['action']}."
            )
        if avg_time:
            narrative_parts.append(
                "Fastest resolution starts with: "
                f"{avg_time[0]['first_action']}."
            )

        return {
            "insight_type": "operator_intelligence",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "total_resolved": total_resolved,
            "total_unresolved": total_unresolved,
            "action_lift": action_lift[:10],
            "fastest_resolution_paths": avg_time[:5],
        }

    return await run_in_threadpool(_analyze)
