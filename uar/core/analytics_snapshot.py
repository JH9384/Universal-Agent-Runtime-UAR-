"""Single-pass analytics snapshot builder for UAR.

D4A-2 — Operational Optimization

Replaces five independent run-record scans with one shared
aggregation pipeline. Each analytics endpoint extracts its
specific view from the snapshot instead of re-scanning.

Architecture:
    Run Store
        ↓
    build_analytics_snapshot(runs, user, is_admin, hours, limit)
        ↓
    AnalyticsSnapshot
        ↓
    Endpoint-specific extractors
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class SkillFailureCluster:
    skill: str = ""
    count: int = 0
    runs: Set[str] = field(default_factory=set)
    latest: float = 0.0
    latest_error: str = ""
    latest_run_id: str = ""


@dataclass
class ErrorFailureCluster:
    error: str = ""
    count: int = 0
    runs: Set[str] = field(default_factory=set)
    skills: Set[str] = field(default_factory=set)
    latest: float = 0.0


@dataclass
class TopologyNode:
    skill: str = ""
    invocations: int = 0
    successes: int = 0
    failures: int = 0


@dataclass
class TopologyEdge:
    source: str = ""
    target: str = ""
    transitions: int = 0
    failures: int = 0


@dataclass
class HotspotNode:
    skill: str = ""
    invocations: int = 0
    failures: int = 0
    affected_runs: Set[str] = field(default_factory=set)
    latest_run_id: str = ""


@dataclass
class HotspotEdge:
    source: str = ""
    target: str = ""
    transitions: int = 0
    failures: int = 0
    affected_runs: Set[str] = field(default_factory=set)
    latest_run_id: str = ""


@dataclass
class RecipeStat:
    recipe: str = ""
    executions: int = 0
    successes: int = 0
    failures: int = 0
    confidence_sum: float = 0.0
    confidence_count: int = 0
    duration_sum: float = 0.0
    duration_count: int = 0
    last_execution: float = 0.0
    run_ids: Set[str] = field(default_factory=set)


@dataclass
class AnalyticsSnapshot:
    """Raw aggregates produced by a single pass over run records."""

    # Metadata
    runs_loaded: int = 0
    runs_analyzed: int = 0
    limit: int = 0
    truncated: bool = False
    hours: int = 0

    # Failure clusters
    skill_clusters: Dict[str, SkillFailureCluster] = field(
        default_factory=dict
    )
    error_clusters: Dict[str, ErrorFailureCluster] = field(
        default_factory=dict
    )
    total_failures: int = 0

    # Topology hot-paths
    topology_nodes: Dict[str, TopologyNode] = field(
        default_factory=dict
    )
    topology_edges: Dict[str, TopologyEdge] = field(
        default_factory=dict
    )
    topology_recipes: Dict[str, RecipeStat] = field(
        default_factory=dict
    )

    # Failure hotspots
    hotspot_nodes: Dict[str, HotspotNode] = field(
        default_factory=dict
    )
    hotspot_edges: Dict[str, HotspotEdge] = field(
        default_factory=dict
    )
    hotspot_total_failures: int = 0

    # Confidence drift contributors
    skill_failure_counts: Dict[str, int] = field(
        default_factory=dict
    )
    error_failure_counts: Dict[str, int] = field(
        default_factory=dict
    )

    # Recipe intelligence (same data as topology_recipes, filtered view)
    recipe_stats: Dict[str, RecipeStat] = field(
        default_factory=dict
    )


def _to_serializable(obj: Any) -> Any:
    """Recursively convert dataclass sets to lists for JSON."""
    if isinstance(obj, list):
        return [_to_serializable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {
            k: _to_serializable(v)
            for k, v in obj.__dict__.items()
        }
    if isinstance(obj, set):
        return list(obj)
    return obj


def build_analytics_snapshot(
    all_runs: List[Dict[str, Any]],
    user: Optional[str],
    is_admin: bool,
    hours: int,
    limit: int,
) -> AnalyticsSnapshot:
    """Build a snapshot from a list of run records in one pass.

    Args:
        all_runs: Raw records returned by store.list_records().
        user: Current user id (for ownership filtering).
        is_admin: Whether current user is admin.
        hours: Time window (for metadata only).
        limit: Record limit applied (for metadata only).

    Returns:
        AnalyticsSnapshot containing all raw aggregates.
    """
    snapshot = AnalyticsSnapshot(
        runs_loaded=len(all_runs),
        limit=limit,
        truncated=len(all_runs) >= limit,
        hours=hours,
    )

    for run in all_runs:
        owner = run.get("user_id") or run.get("user", "")
        if owner and owner != user and not is_admin:
            continue

        snapshot.runs_analyzed += 1
        run_id = run.get("run_id") or run.get("id", "")
        status_ok = run.get("status") == "success"
        skills = run.get("skills") or []
        events = run.get("events") or []
        meta = run.get("metadata") or {}
        exec_order = meta.get("execution_order") or []
        conf = run.get("replay_confidence") or run.get("confidence")
        if isinstance(conf, dict):
            conf = conf.get("score")
        conf_score = float(conf) if conf is not None else None
        dur = run.get("duration_ms", 0) or 0
        ts = run.get("created_at") or run.get("timestamp", 0) or 0

        # ---- Failure clusters + Confidence drift ----
        failed_skills: Set[str] = set()
        for ev in events:
            is_fail = ev.get("error") or ev.get("type") == "error"
            if not is_fail:
                continue
            snapshot.total_failures += 1
            skill = ev.get("skill", "unknown")
            err_msg = str(ev.get("error", ev.get("message", "unknown")))
            err_key = err_msg[:80]
            ev_ts = ev.get("timestamp", ts)

            # Skill cluster
            sc = snapshot.skill_clusters.setdefault(
                skill, SkillFailureCluster(skill=skill)
            )
            sc.count += 1
            sc.runs.add(run_id)
            if ev_ts > sc.latest:
                sc.latest = ev_ts
                sc.latest_error = err_msg[:120]
                sc.latest_run_id = run_id

            # Error cluster
            ec = snapshot.error_clusters.setdefault(
                err_key, ErrorFailureCluster(error=err_key)
            )
            ec.count += 1
            ec.runs.add(run_id)
            ec.skills.add(skill)
            if ev_ts > ec.latest:
                ec.latest = ev_ts

            # Confidence-drift contributors
            snapshot.skill_failure_counts[skill] = (
                snapshot.skill_failure_counts.get(skill, 0) + 1
            )
            err_short = err_msg[:60]
            snapshot.error_failure_counts[err_short] = (
                snapshot.error_failure_counts.get(err_short, 0) + 1
            )

            # Hotspot failure detection
            if skill:
                failed_skills.add(skill)

        # ---- Topology hot-paths ----
        for skill in skills:
            node = snapshot.topology_nodes.setdefault(
                skill, TopologyNode(skill=skill)
            )
            node.invocations += 1
            if status_ok:
                node.successes += 1
            else:
                node.failures += 1

        for i in range(len(skills) - 1):
            src = skills[i]
            dst = skills[i + 1]
            key = f"{src}\u2192{dst}"
            edge = snapshot.topology_edges.setdefault(
                key, TopologyEdge(source=src, target=dst)
            )
            edge.transitions += 1
            if not status_ok:
                edge.failures += 1

        for item in exec_order:
            if isinstance(item, dict) and item.get("type") == "recipe":
                rid = item.get("content", item.get("id", "unknown"))
                rec = snapshot.topology_recipes.setdefault(
                    rid, RecipeStat(recipe=rid)
                )
                rec.executions += 1
                if status_ok:
                    rec.successes += 1
                else:
                    rec.failures += 1
                if conf_score is not None:
                    rec.confidence_sum += conf_score
                    rec.confidence_count += 1
                if dur:
                    rec.duration_sum += dur
                    rec.duration_count += 1
                if ts > rec.last_execution:
                    rec.last_execution = ts
                rec.run_ids.add(run_id)

        # ---- Failure hotspots ----
        snapshot.hotspot_total_failures += len(failed_skills)
        for skill in skills:
            hn = snapshot.hotspot_nodes.setdefault(
                skill, HotspotNode(skill=skill)
            )
            hn.invocations += 1
            if skill in failed_skills:
                hn.failures += 1
                hn.affected_runs.add(run_id)
                hn.latest_run_id = run_id

        for i in range(len(skills) - 1):
            src = skills[i]
            dst = skills[i + 1]
            key = f"{src}\u2192{dst}"
            he = snapshot.hotspot_edges.setdefault(
                key, HotspotEdge(source=src, target=dst)
            )
            he.transitions += 1
            if src in failed_skills or dst in failed_skills:
                he.failures += 1
                he.affected_runs.add(run_id)
                he.latest_run_id = run_id

    # Alias recipe_stats to topology_recipes (same data)
    snapshot.recipe_stats = snapshot.topology_recipes

    return snapshot


def extract_failure_clusters(
    snapshot: AnalyticsSnapshot, top: int
) -> dict:
    """Extract failure-clusters response from snapshot."""
    skill_list = sorted(
        snapshot.skill_clusters.values(),
        key=lambda x: x.count,
        reverse=True,
    )[:top]
    error_list = sorted(
        snapshot.error_clusters.values(),
        key=lambda x: x.count,
        reverse=True,
    )[:top]

    return {
        "hours": snapshot.hours,
        "total_runs_scanned": snapshot.runs_analyzed,
        "total_failures": snapshot.total_failures,
        "top_skills": [
            {
                "skill": sc.skill,
                "count": sc.count,
                "run_count": len(sc.runs),
                "run_ids": list(sc.runs),
                "latest": sc.latest,
                "latest_error": sc.latest_error,
                "latest_run_id": sc.latest_run_id,
            }
            for sc in skill_list
        ],
        "top_errors": [
            {
                "error": ec.error,
                "count": ec.count,
                "run_count": len(ec.runs),
                "run_ids": list(ec.runs),
                "skill_count": len(ec.skills),
                "latest": ec.latest,
            }
            for ec in error_list
        ],
    }


def extract_topology_hot_paths(
    snapshot: AnalyticsSnapshot, top: int
) -> dict:
    """Extract topology/hot-paths response from snapshot."""
    node_list = sorted(
        snapshot.topology_nodes.values(),
        key=lambda x: x.invocations,
        reverse=True,
    )[:top]
    edge_list = sorted(
        snapshot.topology_edges.values(),
        key=lambda x: x.transitions,
        reverse=True,
    )[:top]
    recipe_list = sorted(
        snapshot.topology_recipes.values(),
        key=lambda x: x.executions,
        reverse=True,
    )[:top]

    nodes = []
    for n in node_list:
        total = n.invocations
        nodes.append({
            "skill": n.skill,
            "invocations": n.invocations,
            "success_rate": round(n.successes / total, 2) if total else 0,
        })

    edges = []
    for e in edge_list:
        total = e.transitions
        edges.append({
            "source": e.source,
            "target": e.target,
            "transitions": e.transitions,
            "success_rate": round(
                (total - e.failures) / total, 2
            ) if total else 0,
        })

    recipes = []
    for r in recipe_list:
        total = r.executions
        recipes.append({
            "recipe": r.recipe,
            "executions": r.executions,
            "success_rate": round(r.successes / total, 2) if total else 0,
        })

    return {
        "hours": snapshot.hours,
        "total_runs": snapshot.runs_analyzed,
        "nodes": nodes,
        "edges": edges,
        "recipes": recipes,
    }


def _severity(failure_rate: float) -> str:
    if failure_rate >= 0.5:
        return "critical"
    if failure_rate >= 0.2:
        return "warning"
    return "healthy"


def extract_failure_hotspots(
    snapshot: AnalyticsSnapshot, top: int
) -> dict:
    """Extract topology/failure-hotspots response from snapshot."""
    node_list = []
    for n in snapshot.hotspot_nodes.values():
        inv = n.invocations
        fr = n.failures / inv if inv else 0
        node_list.append({
            "skill": n.skill,
            "invocations": n.invocations,
            "failures": n.failures,
            "failure_rate": round(fr, 2),
            "severity": _severity(fr),
            "affected_runs": len(n.affected_runs),
            "run_ids": list(n.affected_runs),
            "latest_run_id": n.latest_run_id,
        })

    edge_list = []
    for e in snapshot.hotspot_edges.values():
        tr = e.transitions
        fr = e.failures / tr if tr else 0
        edge_list.append({
            "source": e.source,
            "target": e.target,
            "transitions": e.transitions,
            "failures": e.failures,
            "failure_rate": round(fr, 2),
            "severity": _severity(fr),
            "affected_runs": len(e.affected_runs),
            "run_ids": list(e.affected_runs),
            "latest_run_id": e.latest_run_id,
        })

    node_list = sorted(
        node_list, key=lambda x: x["failure_rate"], reverse=True
    )[:top]
    edge_list = sorted(
        edge_list, key=lambda x: x["failure_rate"], reverse=True
    )[:top]

    return {
        "hours": snapshot.hours,
        "total_runs": snapshot.runs_analyzed,
        "total_failures": snapshot.hotspot_total_failures,
        "nodes": node_list,
        "edges": edge_list,
    }


def extract_recipe_intelligence(
    snapshot: AnalyticsSnapshot,
) -> dict:
    """Extract recipes/intelligence response from snapshot."""
    recipe_list = []
    for rec in snapshot.recipe_stats.values():
        total = rec.executions
        sr = round(rec.successes / total, 2) if total else 0
        fr = round(rec.failures / total, 2) if total else 0
        avg_conf = (
            round(rec.confidence_sum / rec.confidence_count, 2)
            if rec.confidence_count
            else None
        )
        avg_dur = (
            int(rec.duration_sum / rec.duration_count)
            if rec.duration_count
            else None
        )

        if sr >= 0.9 and total >= 3:
            classification = "recommended"
        elif fr >= 0.5 or (sr < 0.5 and total >= 3):
            classification = "retire"
        else:
            classification = "monitor"

        recipe_list.append({
            "recipe": rec.recipe,
            "executions": rec.executions,
            "successes": rec.successes,
            "failures": rec.failures,
            "success_rate": sr,
            "failure_rate": fr,
            "avg_confidence": avg_conf,
            "avg_duration_ms": avg_dur,
            "last_execution": rec.last_execution,
            "classification": classification,
            "run_ids": list(rec.run_ids),
        })

    priority = {"recommended": 0, "monitor": 1, "retire": 2}
    recipe_list.sort(
        key=lambda r: (
            priority.get(r["classification"], 1),
            -r["success_rate"],
        )
    )

    return {
        "hours": snapshot.hours,
        "total_runs": snapshot.runs_analyzed,
        "recipes": recipe_list,
    }


def extract_confidence_drift(
    snapshot: AnalyticsSnapshot,
    mc_history: list,
    burnin_history: list,
    hours: int,
) -> dict:
    """Extract confidence-drift response from snapshot + external history."""
    import time

    cutoff = time.time() - (hours * 3600)

    # Confidence trend from MC history
    conf_scores = [
        s.get("replay_confidence", {}).get("score")
        for s in mc_history
        if s.get("timestamp", 0) >= cutoff
        and s.get("replay_confidence")
        and s["replay_confidence"].get("score") is not None
    ]

    if len(conf_scores) >= 2:
        current_score = conf_scores[-1]
        window_start_score = conf_scores[0]
    elif len(conf_scores) == 1:
        current_score = conf_scores[0]
        window_start_score = None
    else:
        current_score = None
        window_start_score = None

    delta = (
        (current_score or 0) - (window_start_score or 0)
        if current_score is not None and window_start_score is not None
        else 0
    )

    if delta > 5:
        state = "improving"
    elif delta < -5:
        state = "degrading"
    else:
        state = "stable"

    # Failure contributors from snapshot
    top_skill_failures = sorted(
        snapshot.skill_failure_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    top_error_failures = sorted(
        snapshot.error_failure_counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    # Burn-in contributor
    burnin_window = [
        r for r in burnin_history
        if r.get("timestamp", 0) >= cutoff
    ]
    burnin_delta = 0
    if len(burnin_window) >= 2:
        burnin_delta = (
            burnin_window[-1].get("score", 0)
            - burnin_window[0].get("score", 0)
        )

    contributors = []
    if state == "degrading":
        for skill, count in top_skill_failures:
            contributors.append({
                "name": f"{skill} failures",
                "impact": -count,
                "type": "failure",
            })
        for err, count in top_error_failures:
            contributors.append({
                "name": err[:40] + ("\u2026" if len(err) > 40 else ""),
                "impact": -count,
                "type": "error",
            })
        if burnin_delta < 0:
            contributors.append({
                "name": "Burn-In drop",
                "impact": burnin_delta,
                "type": "evidence",
            })
    elif state == "improving":
        if top_skill_failures:
            contributors.append({
                "name": "Fewer skill failures",
                "impact": delta,
                "type": "failure",
            })
        if burnin_delta > 0:
            contributors.append({
                "name": "Burn-In improvement",
                "impact": burnin_delta,
                "type": "evidence",
            })
    else:
        contributors.append({
            "name": "No significant change",
            "impact": 0,
            "type": "stable",
        })

    contributors = contributors[:5]

    return {
        "window_hours": hours,
        "current_score": current_score,
        "window_start_score": window_start_score,
        "delta": delta,
        "state": state,
        "confidence_history": conf_scores,
        "top_contributors": contributors,
        "failure_summary": {
            "total_failures": sum(snapshot.skill_failure_counts.values()),
            "top_skills": [
                {"skill": s, "count": c} for s, c in top_skill_failures
            ],
        },
    }
