"""Fleet Operations API for multi-node UAR deployments.

D4C — Fleet Operations.
Trust Spine Phase: Fleet
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.state import store

security = HTTPBearer(auto_error=False)

router = APIRouter()
logger = logging.getLogger(__name__)

# Fleet registry in-memory cache + lock
_fleet_lock = threading.RLock()
_fleet_registry: Dict[str, "FleetNode"] = {}

# Per-node failure reports (keyed by node_id)
_fleet_failures: Dict[str, List[Dict[str, Any]]] = {}

# Persisted metadata keys
_FLEET_KEY = "__fleet_registry__"
_FLEET_FAILURES_KEY = "__fleet_failures__"
_FLEET_TTL_SECONDS = 300  # 5 minutes

# Minimum nodes to declare a fleet-wide hotspot
_FLEET_HOTSPOT_THRESHOLD = 3


@dataclass(slots=True)
class FleetNode:
    """Health snapshot from a single UAR instance."""

    node_id: str
    node_name: str
    version: str
    health_score: int
    cert_level: str
    active_runs: int
    skills_total: int
    skills_available: int
    circuit_breakers_open: int
    reported_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status()
        d["seconds_since_report"] = int(time.time() - self.reported_at)
        return d

    def status(self) -> str:
        age = time.time() - self.reported_at
        if age <= _FLEET_TTL_SECONDS:
            return "online"
        if age <= _FLEET_TTL_SECONDS * 2:
            return "stale"
        return "offline"

    def is_online(self) -> bool:
        return time.time() - self.reported_at <= _FLEET_TTL_SECONDS


def _load_registry() -> Dict[str, FleetNode]:
    """Load fleet registry from store or return empty dict."""
    try:
        gm = getattr(store, "get_metadata", None)
        if gm is not None and callable(gm):
            raw = store.get_metadata(_FLEET_KEY)
            if raw is not None and isinstance(raw, dict):
                return {
                    k: FleetNode(**v)
                    for k, v in raw.items()
                    if isinstance(v, dict)
                }
    except Exception:
        pass
    return {}


def _save_registry(registry: Dict[str, FleetNode]) -> None:
    """Persist fleet registry to store."""
    try:
        pm = getattr(store, "put_metadata", None)
        if pm is not None and callable(pm):
            payload = {k: asdict(v) for k, v in registry.items()}
            store.put_metadata(_FLEET_KEY, payload)
    except Exception as exc:
        logger.warning("Failed to persist fleet registry: %s", exc)


@router.post("/api/uar/fleet/heartbeat")
async def post_fleet_heartbeat(
    payload: Dict[str, Any],
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Register or update a fleet node health snapshot."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    node_id = str(payload.get("node_id", ""))
    if not node_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_node_id",
                "message": "node_id is required",
            },
        )

    node = FleetNode(
        node_id=node_id,
        node_name=str(payload.get("node_name", node_id)),
        version=str(payload.get("version", "unknown")),
        health_score=int(payload.get("health_score", 0)),
        cert_level=str(payload.get("cert_level", "Experimental")),
        active_runs=int(payload.get("active_runs", 0)),
        skills_total=int(payload.get("skills_total", 0)),
        skills_available=int(payload.get("skills_available", 0)),
        circuit_breakers_open=int(payload.get("circuit_breakers_open", 0)),
        reported_at=time.time(),
    )

    # Optional failure clusters from the node
    failure_clusters = payload.get("failure_clusters")
    if failure_clusters is not None and isinstance(failure_clusters, list):
        await run_in_threadpool(
            _update_node_failures, node_id, failure_clusters
        )

    await run_in_threadpool(_update_node, node)
    return {
        "status": "ok",
        "node_id": node_id,
        "fleet_ttl_seconds": _FLEET_TTL_SECONDS,
    }


def _update_node(node: FleetNode) -> None:
    with _fleet_lock:
        # Lazy-load if in-memory cache is empty
        if not _fleet_registry:
            _fleet_registry.update(_load_registry())
        _fleet_registry[node.node_id] = node
        _save_registry(_fleet_registry)


def _update_node_failures(
    node_id: str, clusters: List[Dict[str, Any]]
) -> None:
    with _fleet_lock:
        if not _fleet_failures:
            _fleet_failures.update(_load_failures())
        # Keep only the latest report per node
        _fleet_failures[node_id] = clusters[:10]  # cap at 10 clusters
        _save_failures(_fleet_failures)


def _load_failures() -> Dict[str, List[Dict[str, Any]]]:
    try:
        gm = getattr(store, "get_metadata", None)
        if gm is not None and callable(gm):
            raw = store.get_metadata(_FLEET_FAILURES_KEY)
            if raw is not None and isinstance(raw, dict):
                return {k: v for k, v in raw.items() if isinstance(v, list)}
    except Exception:
        pass
    return {}


def _save_failures(failures: Dict[str, List[Dict[str, Any]]]) -> None:
    try:
        pm = getattr(store, "put_metadata", None)
        if pm is not None and callable(pm):
            store.put_metadata(_FLEET_FAILURES_KEY, failures)
    except Exception as exc:
        logger.warning("Failed to persist fleet failures: %s", exc)


@router.get("/api/uar/fleet/nodes")
async def get_fleet_nodes(
    show_offline: bool = Query(False),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """List all fleet nodes with health and staleness status."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    registry = await run_in_threadpool(_get_nodes, show_offline)
    return {
        "nodes": [n.to_dict() for n in registry],
        "online_count": sum(1 for n in registry if n.is_online()),
        "total_count": len(registry),
        "ttl_seconds": _FLEET_TTL_SECONDS,
    }


def _get_nodes(show_offline: bool) -> List[FleetNode]:
    with _fleet_lock:
        if not _fleet_registry:
            _fleet_registry.update(_load_registry())
        nodes = list(_fleet_registry.values())

    if not show_offline:
        nodes = [n for n in nodes if n.status() != "offline"]

    # Sort by status (online first), then by health score desc
    nodes.sort(key=lambda n: (0 if n.is_online() else 1, -n.health_score))
    return nodes


@router.get("/api/uar/fleet/health")
async def get_fleet_health(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Aggregate fleet-wide health summary."""
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    nodes = await run_in_threadpool(_get_nodes, False)
    if not nodes:
        return {
            "fleet_health_score": None,
            "nodes_online": 0,
            "nodes_total": 0,
            "critical_nodes": [],
            "cert_distribution": {},
        }

    online = [n for n in nodes if n.is_online()]
    avg_health = (
        int(sum(n.health_score for n in online) / len(online)) if online else 0
    )

    cert_dist: Dict[str, int] = {}
    for n in online:
        cert_dist[n.cert_level] = cert_dist.get(n.cert_level, 0) + 1

    critical = [
        n.to_dict()
        for n in online
        if n.health_score < 50 or n.circuit_breakers_open > 0
    ]

    return {
        "fleet_health_score": avg_health,
        "nodes_online": len(online),
        "nodes_total": len(nodes),
        "critical_nodes": critical,
        "cert_distribution": cert_dist,
    }


@router.get("/api/uar/fleet/failures")
async def get_fleet_failures(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Aggregate failure clusters across the fleet.

    Correlates by skill name + error pattern. Surfaces fleet-wide
    hotspots when the same skill fails on >= 3 nodes.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    result = await run_in_threadpool(_correlate_failures)
    return result


def _correlate_failures() -> Dict[str, Any]:
    with _fleet_lock:
        if not _fleet_failures:
            _fleet_failures.update(_load_failures())
        failures = dict(_fleet_failures)
        nodes = dict(_fleet_registry)

    # Build online node set
    online_ids = {nid for nid, n in nodes.items() if n.is_online()}

    # Aggregate: skill -> list of (node_id, count, error)
    skill_map: Dict[str, List[Dict[str, Any]]] = {}
    for node_id, clusters in failures.items():
        if node_id not in online_ids:
            continue
        for c in clusters:
            if not isinstance(c, dict):
                continue
            skill = str(c.get("skill", c.get("skill_name", "unknown")))
            entry = {
                "node_id": node_id,
                "count": c.get("count", 0),
                "error": c.get("error", c.get("latest_error", "")),
            }
            skill_map.setdefault(skill, []).append(entry)

    # Fleet-wide hotspots
    hotspots = []
    for skill, entries in skill_map.items():
        if len(entries) >= _FLEET_HOTSPOT_THRESHOLD:
            hotspots.append(
                {
                    "skill": skill,
                    "affected_nodes": len(entries),
                    "total_failures": sum(e["count"] for e in entries),
                    "nodes": entries,
                }
            )

    hotspots.sort(key=lambda h: (-h["affected_nodes"], -h["total_failures"]))

    return {
        "hotspots": hotspots,
        "correlated_skills": list(skill_map.keys()),
        "nodes_reporting": len([n for n in online_ids if n in failures]),
    }


@router.get("/api/uar/fleet/routing")
async def get_fleet_routing(
    skill: Optional[str] = Query(None),
    goal: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Rank fleet nodes for executing a given skill or goal.

    Scoring: health_score * 0.4 + skill_availability * 0.3 +
              (no_recent_failures ? 30 : 0).
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    ranked = await run_in_threadpool(_rank_nodes, skill)
    return {
        "recommendations": ranked,
        "skill": skill,
        "goal": goal,
    }


def _rank_nodes(skill: Optional[str]) -> List[Dict[str, Any]]:
    with _fleet_lock:
        if not _fleet_registry:
            _fleet_registry.update(_load_registry())
        nodes = list(_fleet_registry.values())
        if not _fleet_failures:
            _fleet_failures.update(_load_failures())
        failures = dict(_fleet_failures)

    online = [n for n in nodes if n.is_online()]
    if not online:
        return []

    # Build set of (node_id, skill) with recent failures
    failing_pairs: set = set()
    for node_id, clusters in failures.items():
        for c in clusters:
            if not isinstance(c, dict):
                continue
            s = str(c.get("skill", c.get("skill_name", "")))
            if s:
                failing_pairs.add((node_id, s))

    results = []
    for n in online:
        score = 0.0
        score += min(n.health_score, 100) * 0.40
        score += min(n.skills_available, 100) * 0.30
        # Penalise if skill recently failed on this node
        if skill and (n.node_id, skill) in failing_pairs:
            score -= 30.0
        else:
            score += 30.0
        # Penalise open circuit breakers
        score -= n.circuit_breakers_open * 10.0

        score = max(0.0, min(100.0, score))
        results.append(
            {
                "node_id": n.node_id,
                "node_name": n.node_name,
                "score": int(round(score)),
                "health_score": n.health_score,
                "skills_available": n.skills_available,
                "cert_level": n.cert_level,
            }
        )

    results.sort(key=lambda r: -r["score"])
    return results


__all__ = ["router", "FleetNode", "_FLEET_TTL_SECONDS"]
