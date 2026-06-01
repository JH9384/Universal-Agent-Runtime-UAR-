"""Operator Workflow API — Morning Briefing, Incident Workbench,
Trust Explorer, Knowledge Graph, Time Machine.

Trust Spine Phase: T7 — Operational Intelligence Platform
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()

# ------------------------------------------------------------------
# Morning Briefing
# ------------------------------------------------------------------


@router.get("/api/uar/briefing")
async def get_briefing(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Aggregate daily operational intelligence for operators."""
    auth_middleware(credentials)

    drift_events = 0
    trust_drops = 0
    open_incidents = 0
    unresolved_count = 0
    top_trusted = None
    top_score = 0.0
    trust_stable = True

    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = compute_trust(outcomes, metadata)
        types = trust_result.get("recommendation_types", [])

        for t in types:
            if t.get("drift_penalty", 0) > 0:
                drift_events += 1
            score = t.get("trust_score", 0)
            if score > top_score:
                top_score = score
                top_trusted = t.get("type")

        # Compare to yesterday's snapshot if available
        yesterday = _get_snapshot_for_day(int(time.time()) - 86400)
        if yesterday and "trust" in yesterday:
            old_types = yesterday["trust"].get("recommendation_types", [])
            old_map = {t["type"]: t.get("trust_score", 0) for t in old_types}
            for t in types:
                old = old_map.get(t["type"], t.get("trust_score", 0))
                if t.get("trust_score", 0) < old - 0.10:
                    trust_drops += 1

        if trust_drops >= 3:
            trust_stable = False
    except Exception as exc:
        logger.warning("briefing trust computation failed: %s", exc)

    # Count open incidents
    try:
        open_incidents = len(
            [i for i in _load_all_incidents() if i.get("status") != "resolved"]
        )
    except Exception:
        pass

    # Count unresolved recommendations (no outcome)
    try:
        outcomes = store.get_outcomes(limit=5000)
        resolved_ids = {o.get("recommendation_id") for o in outcomes}
        metadata = store.get_recommendation_metadata(limit=5000)
        unresolved_count = sum(
            1
            for m in metadata
            if m.get("recommendation_id") not in resolved_ids
        )
    except Exception:
        pass

    greeting = _greeting_for_hour()

    return {
        "greeting": greeting,
        "generated_at": int(time.time()),
        "drift_events": drift_events,
        "trust_drops": trust_drops,
        "trust_stable": trust_stable,
        "open_incidents": open_incidents,
        "unresolved_recommendations": unresolved_count,
        "top_trusted_type": top_trusted,
        "top_trust_score": round(top_score, 2) if top_trusted else None,
        "summary_text": _build_narrative(
            greeting, drift_events, trust_drops, open_incidents, trust_stable
        ),
    }


def _greeting_for_hour() -> str:
    import datetime

    h = datetime.datetime.now().hour
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def _build_narrative(
    greeting: str,
    drift: int,
    drops: int,
    incidents: int,
    stable: bool,
) -> str:
    parts = [f"{greeting}."]
    if drift:
        parts.append(f"{drift} drift event(s).")
    if drops:
        parts.append(f"{drops} trust drop(s).")
    if incidents:
        parts.append(f"{incidents} open incident(s).")
    if stable and not drift and not drops:
        parts.append("Trust stable. No anomalies.")
    return " ".join(parts)


# ------------------------------------------------------------------
# Trust Explorer
# ------------------------------------------------------------------


@router.get("/api/uar/trust-explorer/{rec_type}")
async def get_trust_explorer(
    rec_type: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Detailed trust breakdown for a single recommendation type."""
    auth_middleware(credentials)

    try:
        from uar.core.trust_engine import compute_trust
        from uar.core.effectiveness_ranking import compute_effectiveness
        from uar.core.evidence import aggregate_evidence
        from uar.core.calibration import compute_calibration

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)

        trust_result = compute_trust(outcomes, metadata)
        type_data = None
        for t in trust_result.get("recommendation_types", []):
            if t.get("type") == rec_type:
                type_data = t
                break

        if not type_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Type '{rec_type}' not found",
            )

        # Component-level detail
        eff = compute_effectiveness(outcomes, metadata)
        eff_type = next(
            (
                e
                for e in eff.get("recommendation_types", [])
                if e.get("type") == rec_type
            ),
            {},
        )

        cal = compute_calibration(outcomes, metadata)
        cal_type = next(
            (c for c in cal.get("types", []) if c.get("type") == rec_type),
            {},
        )

        ev = aggregate_evidence(outcomes, metadata)
        ev_type = next(
            (
                e
                for e in ev.get("recommendation_types", [])
                if e.get("type") == rec_type
            ),
            {},
        )

        return {
            "type": rec_type,
            "trust_score": type_data.get("trust_score"),
            "effectiveness": {
                "score": eff_type.get("weighted_resolution_rate"),
                "resolved": eff_type.get("resolved_count", 0),
                "total": eff_type.get("total_count", 0),
                "drift_penalty": eff_type.get("drift_penalty", 0),
            },
            "calibration": {
                "score": cal_type.get("calibration_score"),
                "error": cal_type.get("calibration_error"),
                "bucket": cal_type.get("bucket"),
            },
            "evidence": {
                "score": ev_type.get("evidence_score"),
                "sample_size": ev_type.get("sample_size", 0),
                "resolution_rate": ev_type.get("resolution_rate"),
            },
            "generated_at": int(time.time()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trust explorer failed for %s: %s", rec_type, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trust computation failed",
        )


# ------------------------------------------------------------------
# Incident Workbench
# ------------------------------------------------------------------

_INCIDENT_NAMESPACE = "operator:incident"


def _incident_key(incident_id: str) -> str:
    return f"{_INCIDENT_NAMESPACE}:{incident_id}"


def _load_all_incidents() -> List[Dict[str, Any]]:
    """Load incidents from store metadata (with in-memory fallback)."""
    incidents: List[Dict[str, Any]] = []
    seen: set = set()

    # Attempt store load
    if hasattr(store, "list_meta_keys"):
        try:
            keys = store.list_meta_keys()
            for key in keys:
                if key.startswith(f"{_INCIDENT_NAMESPACE}:"):
                    raw = store.get_metadata(key)
                    if raw:
                        ev = json.loads(raw) if isinstance(raw, str) else raw
                        iid = ev.get("id")
                        if iid and iid not in seen:
                            seen.add(iid)
                            incidents.append(ev)
        except Exception:
            pass

    # Fallback: scan for keys starting with incident prefix via get_metadata
    # (list_meta_keys may not exist on all stores)
    try:
        # Try a few sequential IDs — incidents are created with timestamps
        for i in range(100):
            test_key = f"{_INCIDENT_NAMESPACE}:incident-{i}"
            raw = store.get_metadata(test_key)
            if raw:
                ev = json.loads(raw) if isinstance(raw, str) else raw
                iid = ev.get("id")
                if iid and iid not in seen:
                    seen.add(iid)
                    incidents.append(ev)
    except Exception:
        pass

    return sorted(
        incidents, key=lambda x: x.get("created_at", 0), reverse=True
    )


def _persist_incident(incident: Dict[str, Any]) -> None:
    key = _incident_key(incident["id"])
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, incident)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, json.dumps(incident))
    except Exception as exc:
        logger.warning("incident persistence failed: %s", exc)


@router.get("/api/uar/incidents")
async def list_incidents(
    status: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List all incidents, optionally filtered by status."""
    auth_middleware(credentials)
    incidents = _load_all_incidents()
    if status:
        incidents = [i for i in incidents if i.get("status") == status]
    return incidents


@router.post("/api/uar/incidents")
async def create_incident(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Create a new incident."""
    auth_middleware(credentials)
    import uuid

    incident_id = f"incident-{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    incident = {
        "id": incident_id,
        "title": body.get("title", "Untitled Incident"),
        "description": body.get("description", ""),
        "status": body.get("status", "open"),
        "severity": body.get("severity", "medium"),
        "linked_run_ids": body.get("linked_run_ids", []),
        "linked_rec_ids": body.get("linked_rec_ids", []),
        "resolution_notes": body.get("resolution_notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    _persist_incident(incident)
    return incident


@router.get("/api/uar/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a single incident."""
    auth_middleware(credentials)
    for inc in _load_all_incidents():
        if inc.get("id") == incident_id:
            return inc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Incident not found",
    )


@router.put("/api/uar/incidents/{incident_id}")
async def update_incident(
    incident_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Update an incident."""
    auth_middleware(credentials)
    for inc in _load_all_incidents():
        if inc.get("id") == incident_id:
            for field in (
                "title",
                "description",
                "status",
                "severity",
                "linked_run_ids",
                "linked_rec_ids",
                "resolution_notes",
            ):
                if field in body:
                    inc[field] = body[field]
            inc["updated_at"] = int(time.time())
            _persist_incident(inc)
            return inc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Incident not found",
    )


@router.delete("/api/uar/incidents/{incident_id}")
async def delete_incident(
    incident_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Delete an incident."""
    auth_middleware(credentials)
    key = _incident_key(incident_id)
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, None)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, "null")
    except Exception:
        pass
    return {"deleted": incident_id}


# ------------------------------------------------------------------
# Knowledge Graph
# ------------------------------------------------------------------


@router.get("/api/uar/graph/{run_id}")
async def get_knowledge_graph(
    run_id: str,
    depth: int = Query(2, ge=1, le=4),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return a knowledge graph centered on a run."""
    auth_middleware(credentials)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen: set = set()

    # Center node: run
    nodes.append(
        {
            "id": run_id,
            "type": "run",
            "label": run_id,
        }
    )
    seen.add(run_id)

    # Link to record
    try:
        rec = store.get_by_run_id(run_id)
        if rec:
            goal_id = (
                getattr(rec, "goal_id", None) or rec.goal.get("id")
                if hasattr(rec, "goal")
                else None
            )
            if goal_id and goal_id not in seen:
                nodes.append(
                    {
                        "id": goal_id,
                        "type": "goal",
                        "label": goal_id,
                    }
                )
                seen.add(goal_id)
                edges.append(
                    {"source": run_id, "target": goal_id, "type": "has_goal"}
                )
    except Exception:
        pass

    # Recommendations linked to this run
    try:
        metadata = store.get_recommendation_metadata(limit=5000)
        for m in metadata:
            if m.get("run_id") == run_id:
                rid = m.get("recommendation_id")
                if rid and rid not in seen:
                    nodes.append(
                        {
                            "id": rid,
                            "type": "recommendation",
                            "label": m.get("title", rid),
                            "category": m.get("category"),
                        }
                    )
                    seen.add(rid)
                    edges.append(
                        {
                            "source": run_id,
                            "target": rid,
                            "type": "has_recommendation",
                        }
                    )

                    # Outcomes for this recommendation
                    if depth >= 2:
                        outcomes = store.get_outcomes(limit=5000)
                        for o in outcomes:
                            if o.get("recommendation_id") == rid:
                                oid = f"outcome:{rid}"
                                if oid not in seen:
                                    nodes.append(
                                        {
                                            "id": oid,
                                            "type": "outcome",
                                            "label": o.get(
                                                "outcome_type", "unknown"
                                            ),
                                        }
                                    )
                                    seen.add(oid)
                                    edges.append(
                                        {
                                            "source": rid,
                                            "target": oid,
                                            "type": "has_outcome",
                                        }
                                    )
    except Exception:
        pass

    # Incidents linked to this run
    try:
        for inc in _load_all_incidents():
            if run_id in inc.get("linked_run_ids", []):
                iid = inc["id"]
                if iid not in seen:
                    nodes.append(
                        {
                            "id": iid,
                            "type": "incident",
                            "label": inc.get("title", iid),
                            "status": inc.get("status"),
                        }
                    )
                    seen.add(iid)
                    edges.append(
                        {
                            "source": run_id,
                            "target": iid,
                            "type": "has_incident",
                        }
                    )
    except Exception:
        pass

    return {"nodes": nodes, "edges": edges}


# ------------------------------------------------------------------
# Time Machine
# ------------------------------------------------------------------

_SNAPSHOT_NAMESPACE = "operator:snapshot"


def _snapshot_key(timestamp: int) -> str:
    return f"{_SNAPSHOT_NAMESPACE}:{timestamp}"


def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    key = _snapshot_key(snapshot["timestamp"])
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, snapshot)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, json.dumps(snapshot))
    except Exception as exc:
        logger.warning("snapshot persistence failed: %s", exc)


def _get_snapshot_for_day(day_timestamp: int) -> Optional[Dict[str, Any]]:
    """Find closest snapshot to a given day."""
    try:
        # Try exact hour boundaries
        for hour in range(24):
            ts = (day_timestamp // 86400) * 86400 + hour * 3600
            key = _snapshot_key(ts)
            raw = store.get_metadata(key)
            if raw:
                return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass
    return None


def _load_all_snapshots(limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent snapshots."""
    snapshots: List[Dict[str, Any]] = []
    seen: set = set()
    # Scan recent hours
    now = int(time.time())
    for h in range(limit):
        ts = now - h * 3600
        try:
            key = _snapshot_key(ts)
            raw = store.get_metadata(key)
            if raw:
                snap = json.loads(raw) if isinstance(raw, str) else raw
                ts_val = snap.get("timestamp")
                if ts_val and ts_val not in seen:
                    seen.add(ts_val)
                    snapshots.append(snap)
        except Exception:
            pass
    return sorted(snapshots, key=lambda x: x.get("timestamp", 0), reverse=True)


@router.get("/api/uar/snapshots")
async def list_snapshots(
    limit: int = Query(24, ge=1, le=168),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List historical snapshots."""
    auth_middleware(credentials)
    return _load_all_snapshots(limit=limit)


@router.post("/api/uar/snapshots")
async def create_snapshot(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Capture a new operational snapshot."""
    auth_middleware(credentials)

    now = int(time.time())
    snap: Dict[str, Any] = {"timestamp": now, "captured_at": now}

    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        snap["trust"] = compute_trust(outcomes, metadata)
    except Exception as exc:
        logger.warning("snapshot trust capture failed: %s", exc)
        snap["trust"] = None

    try:
        recs = store.get_recommendation_metadata(limit=5000)
        snap["recommendation_count"] = len(recs)
    except Exception:
        snap["recommendation_count"] = 0

    try:
        runs = store.list_records(limit=100)
        snap["recent_run_ids"] = [
            getattr(r, "run_id", r.get("run_id")) for r in runs[:10]
        ]
    except Exception:
        snap["recent_run_ids"] = []

    _persist_snapshot(snap)
    return snap


@router.get("/api/uar/snapshots/{timestamp}")
async def get_snapshot(
    timestamp: int,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a specific snapshot."""
    auth_middleware(credentials)
    key = _snapshot_key(timestamp)
    raw = store.get_metadata(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
    snap = json.loads(raw) if isinstance(raw, str) else raw
    return snap
