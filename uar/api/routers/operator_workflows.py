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


# ------------------------------------------------------------------
# Recommendation Inbox
# ------------------------------------------------------------------

_INBOX_NAMESPACE = "operator:inbox"


def _inbox_key(item_id: str) -> str:
    return f"{_INBOX_NAMESPACE}:{item_id}"


def _load_all_inbox_items() -> List[Dict[str, Any]]:
    """Load inbox items from store metadata."""
    items: List[Dict[str, Any]] = []
    seen: set = set()
    try:
        for i in range(200):
            test_key = f"{_INBOX_NAMESPACE}:item-{i}"
            raw = store.get_metadata(test_key)
            if raw:
                ev = json.loads(raw) if isinstance(raw, str) else raw
                iid = ev.get("id")
                if iid and iid not in seen:
                    seen.add(iid)
                    items.append(ev)
    except Exception:
        pass
    return sorted(items, key=lambda x: x.get("created_at", 0), reverse=True)


def _persist_inbox_item(item: Dict[str, Any]) -> None:
    key = _inbox_key(item["id"])
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, item)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, json.dumps(item))
    except Exception as exc:
        logger.warning("inbox persistence failed: %s", exc)


def _generate_inbox_items() -> List[Dict[str, Any]]:
    """Generate inbox items from current recommendations."""
    items: List[Dict[str, Any]] = []
    existing = {i["source_rec_id"]: i for i in _load_all_inbox_items()}
    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = compute_trust(outcomes, metadata)
        trust_by_type = {
            t["type"]: t for t in trust_result.get("recommendation_types", [])
        }
        for meta in metadata:
            rid = meta.get("recommendation_id")
            if not rid:
                continue
            if rid in existing:
                items.append(existing[rid])
                continue
            cat = meta.get("category", "")
            trust = trust_by_type.get(cat, {})
            item = {
                "id": f"inbox-{rid}",
                "source_rec_id": rid,
                "title": meta.get("title", ""),
                "category": cat,
                "confidence": meta.get("confidence", 0.0),
                "trust_score": trust.get("trust_score"),
                "drift_penalty": trust.get("drift_penalty"),
                "status": "new",
                "assigned_to": None,
                "notes": "",
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
            }
            _persist_inbox_item(item)
            items.append(item)
    except Exception as exc:
        logger.warning("inbox generation failed: %s", exc)
    return items


@router.get("/api/uar/inbox")
async def get_inbox(
    status: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List recommendation inbox items."""
    auth_middleware(credentials)
    items = _generate_inbox_items()
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


@router.put("/api/uar/inbox/{item_id}")
async def update_inbox_item(
    item_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Update an inbox item (status, assignment, notes)."""
    auth_middleware(credentials)
    for item in _load_all_inbox_items():
        if item.get("id") == item_id:
            for field in ("status", "assigned_to", "notes"):
                if field in body:
                    item[field] = body[field]
            item["updated_at"] = int(time.time())
            _persist_inbox_item(item)
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Inbox item not found",
    )


# ------------------------------------------------------------------
# Unified Investigation Flow
# ------------------------------------------------------------------


@router.get("/api/uar/investigate/{run_id}")
async def get_investigation_flow(
    run_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return a guided investigation flow for a run."""
    auth_middleware(credentials)

    steps: List[Dict[str, Any]] = []

    # Step 1: Replay summary
    try:
        rec = store.get_by_run_id(run_id)
        if rec:
            steps.append(
                {
                    "step": 1,
                    "title": "Review Run",
                    "type": "replay",
                    "description": f"Run {run_id} — "
                    f"{getattr(rec, 'status', 'unknown')}",
                    "action": "Open Replay Explorer",
                    "link": f"/api/uar/replay/{run_id}",
                }
            )
    except Exception:
        pass

    # Step 2: Recommendations affecting this run
    try:
        metadata = store.get_recommendation_metadata(limit=5000)
        affecting = [m for m in metadata if m.get("run_id") == run_id]
        if affecting:
            steps.append(
                {
                    "step": 2,
                    "title": "Review Recommendations",
                    "type": "recommendations",
                    "description": f"{len(affecting)} recommendation(s) "
                    "linked to this run",
                    "action": "View Trust Overlay",
                    "items": [
                        {
                            "rec_id": m["recommendation_id"],
                            "title": m.get("title", ""),
                        }
                        for m in affecting
                    ],
                }
            )
    except Exception:
        pass

    # Step 3: Check for incidents
    incidents = [
        inc
        for inc in _load_all_incidents()
        if run_id in inc.get("linked_run_ids", [])
    ]
    if incidents:
        steps.append(
            {
                "step": 3,
                "title": "Existing Incidents",
                "type": "incidents",
                "description": f"{len(incidents)} incident(s) linked",
                "action": "Open Incident Workbench",
                "items": [
                    {"id": i["id"], "title": i["title"], "status": i["status"]}
                    for i in incidents
                ],
            }
        )
    else:
        steps.append(
            {
                "step": 3,
                "title": "Create Incident",
                "type": "incident_action",
                "description": "No incident linked. Create one?",
                "action": "Create Incident",
                "suggested_title": f"Investigate run {run_id}",
            }
        )

    # Step 4: Knowledge graph
    steps.append(
        {
            "step": 4,
            "title": "Explore Connections",
            "type": "graph",
            "description": "Visual graph of related entities",
            "action": "Open Knowledge Graph",
            "link": f"/api/uar/graph/{run_id}",
        }
    )

    # Step 5: Capture snapshot
    steps.append(
        {
            "step": 5,
            "title": "Capture Snapshot",
            "type": "snapshot",
            "description": "Save current state for comparison",
            "action": "Capture Snapshot",
            "link": "/api/uar/snapshots",
        }
    )

    return {
        "run_id": run_id,
        "steps": steps,
        "generated_at": int(time.time()),
    }


# ------------------------------------------------------------------
# Knowledge Graph v2 — expanded nodes
# ------------------------------------------------------------------


@router.get("/api/uar/graph-v2/{center_id}")
async def get_knowledge_graph_v2(
    center_id: str,
    center_type: str = Query("run"),
    depth: int = Query(2, ge=1, le=4),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Expanded knowledge graph with operator, alert, snapshot nodes."""
    auth_middleware(credentials)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen: set = set()

    def add_node(node_id: str, ntype: str, label: str, **extra) -> None:
        if node_id not in seen:
            seen.add(node_id)
            nodes.append(
                {"id": node_id, "type": ntype, "label": label, **extra}
            )

    def add_edge(src: str, tgt: str, etype: str) -> None:
        edges.append({"source": src, "target": tgt, "type": etype})

    add_node(center_id, center_type, center_id)

    if center_type == "run":
        run_id = center_id
        try:
            rec = store.get_by_run_id(run_id)
            if rec:
                goal_id = getattr(rec, "goal_id", None)
                if goal_id:
                    add_node(goal_id, "goal", goal_id)
                    add_edge(run_id, goal_id, "has_goal")
        except Exception:
            pass

        try:
            metadata = store.get_recommendation_metadata(limit=5000)
            for m in metadata:
                if m.get("run_id") == run_id:
                    rid = m["recommendation_id"]
                    add_node(
                        rid,
                        "recommendation",
                        m.get("title", rid),
                        category=m.get("category"),
                    )
                    add_edge(run_id, rid, "has_recommendation")

                    if depth >= 2:
                        outcomes = store.get_outcomes(limit=5000)
                        for o in outcomes:
                            if o.get("recommendation_id") == rid:
                                oid = f"outcome:{rid}"
                                add_node(
                                    oid,
                                    "outcome",
                                    o.get("outcome_type", "unknown"),
                                )
                                add_edge(rid, oid, "has_outcome")
        except Exception:
            pass

        # Alerts via alert_tracker metadata
        try:
            for i in range(50):
                key = f"alert_tracker:alert-{i}"
                raw = store.get_metadata(key)
                if raw:
                    ev = json.loads(raw) if isinstance(raw, str) else raw
                    if run_id in str(ev.get("data", "")):
                        aid = ev.get("id", f"alert-{i}")
                        add_node(aid, "alert", ev.get("type", "alert"))
                        add_edge(run_id, aid, "has_alert")
        except Exception:
            pass

    # Link incidents regardless of center type
    for inc in _load_all_incidents():
        if center_id in inc.get("linked_run_ids", []):
            iid = inc["id"]
            add_node(
                iid,
                "incident",
                inc.get("title", iid),
                status=inc.get("status"),
            )
            add_edge(center_id, iid, "has_incident")

    # Link snapshots that mention this center
    try:
        for snap in _load_all_snapshots(limit=50):
            if center_id in snap.get("recent_run_ids", []):
                sid = f"snap:{snap['timestamp']}"
                add_node(sid, "snapshot", f"Snap {snap['timestamp']}")
                add_edge(center_id, sid, "has_snapshot")
    except Exception:
        pass

    # Operator nodes linked via incidents
    for inc in _load_all_incidents():
        if center_id in (inc.get("linked_run_ids", []) + [center_id]):
            assignee = inc.get("assigned_to") or inc.get("operator")
            if assignee:
                oid = f"op:{assignee}"
                add_node(oid, "operator", assignee)
                add_edge(inc["id"], oid, "assigned_to")

    return {"nodes": nodes, "edges": edges}


# ------------------------------------------------------------------
# Report Generation
# ------------------------------------------------------------------


@router.get("/api/uar/reports/trust-validation")
async def get_trust_validation_report(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Generate a human-readable trust validation report."""
    auth_middleware(credentials)

    try:
        from uar.core.trust_engine import compute_trust
        from uar.core.effectiveness_ranking import compute_effectiveness

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = compute_trust(outcomes, metadata)
        eff_result = compute_effectiveness(outcomes, metadata)
        trust_types = trust_result.get("recommendation_types", [])
        eff_types = eff_result.get("recommendation_types", [])

        # Distribution
        bands = {
            "highly_trusted": 0,
            "trusted": 0,
            "watch": 0,
            "weak": 0,
            "untrusted": 0,
        }
        for t in trust_types:
            score = t.get("trust_score", 0.0)
            if score >= 0.80:
                bands["highly_trusted"] += 1
            elif score >= 0.60:
                bands["trusted"] += 1
            elif score >= 0.40:
                bands["watch"] += 1
            elif score >= 0.20:
                bands["weak"] += 1
            else:
                bands["untrusted"] += 1

        # Correlation
        corr = None
        try:
            from scipy.stats import spearmanr

            eff_map = {
                t["type"]: t.get("resolution_rate", 0.0)
                for t in eff_types
                if "type" in t
            }
            ts, rr = [], []
            for t in trust_types:
                tn = t.get("type", "")
                if tn in eff_map:
                    ts.append(t.get("trust_score", 0.0))
                    rr.append(eff_map[tn])
            if len(ts) >= 3:
                c, _ = spearmanr(ts, rr)
                corr = round(float(c), 3) if c is not None else None
        except Exception:
            pass

        # Drift
        drift = [t for t in trust_types if t.get("drift_penalty", 0) > 0]

        narrative_parts = ["Trust Validation Report"]
        if bands["highly_trusted"] + bands["trusted"] > len(trust_types) * 0.5:
            narrative_parts.append("Most types are in the trusted band.")
        if drift:
            narrative_parts.append(
                f"{len(drift)} type(s) showing drift signals."
            )
        if corr is not None:
            narrative_parts.append(f"Outcome correlation is {corr}.")
        else:
            narrative_parts.append("Insufficient data for correlation.")

        return {
            "report_type": "trust_validation",
            "generated_at": int(time.time()),
            "narrative": " ".join(narrative_parts),
            "trust_distribution": bands,
            "drift_signals": [
                {"type": t["type"], "penalty": t["drift_penalty"]}
                for t in drift
            ],
            "outcome_correlation": corr,
            "type_count": len(trust_types),
            "system_calibration_error": trust_result.get(
                "system_calibration_error"
            ),
        }
    except Exception as exc:
        logger.warning("trust report generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed",
        )


@router.get("/api/uar/reports/burnin-24h")
async def get_burnin_24h_report(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Generate a human-readable 24h burn-in report."""
    auth_middleware(credentials)

    now = int(time.time())
    cutoff = now - 86400

    try:
        snapshots = _load_all_snapshots(limit=24)
        recent = [s for s in snapshots if s.get("timestamp", 0) >= cutoff]

        if not recent:
            return {
                "report_type": "burnin_24h",
                "generated_at": now,
                "narrative": "No snapshots captured in the last 24 hours.",
                "snapshot_count": 0,
                "trust_stable": None,
                "recommendation_growth": None,
            }

        scores = [s.get("recommendation_count", 0) for s in recent]
        trust_counts = [
            len(s.get("trust", {}).get("recommendation_types", []))
            for s in recent
        ]

        first_score = scores[-1] if scores else 0
        last_score = scores[0] if scores else 0
        growth = last_score - first_score

        trust_stable = True
        if len(trust_counts) >= 2:
            first_tc = trust_counts[-1]
            last_tc = trust_counts[0]
            if abs(last_tc - first_tc) > 2:
                trust_stable = False

        narrative_parts = ["24-Hour Burn-In Report"]
        narrative_parts.append(f"{len(recent)} snapshot(s) captured.")
        if growth > 0:
            narrative_parts.append(f"Recommendations increased by {growth}.")
        elif growth < 0:
            narrative_parts.append(
                f"Recommendations decreased by {abs(growth)}."
            )
        else:
            narrative_parts.append("Recommendation count stable.")

        if trust_stable:
            narrative_parts.append("Trust type count stable.")
        else:
            narrative_parts.append("Trust type count changed significantly.")

        return {
            "report_type": "burnin_24h",
            "generated_at": now,
            "narrative": " ".join(narrative_parts),
            "snapshot_count": len(recent),
            "trust_stable": trust_stable,
            "recommendation_growth": growth,
            "latest_recommendation_count": last_score,
            "earliest_recommendation_count": first_score,
        }
    except Exception as exc:
        logger.warning("burnin report generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed",
        )


# ------------------------------------------------------------------
# E1 — Operational Search
# ------------------------------------------------------------------


@router.get("/api/uar/search")
async def search_all(
    q: str = Query(..., min_length=1),
    types: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Unified search across runs, incidents, recommendations, snapshots, alerts."""
    auth_middleware(credentials)
    query = q.lower().strip()
    wanted_types = set(types.split(",") if types else [])
    results: List[Dict[str, Any]] = []

    def add_result(rtype: str, obj: Dict[str, Any], score: int = 1) -> None:
        if wanted_types and rtype not in wanted_types:
            return
        obj["_result_type"] = rtype
        obj["_score"] = score
        results.append(obj)

    # Runs
    try:
        runs = store.list_records(limit=500)
        for r in runs:
            rid = str(getattr(r, "run_id", r.get("run_id", "")))
            if query in rid.lower():
                add_result(
                    "run",
                    {"id": rid, "status": getattr(r, "status", "unknown")},
                    score=10,
                )
    except Exception:
        pass

    # Incidents
    for inc in _load_all_incidents():
        hay = f"{inc.get('title', '')} {inc.get('description', '')} {inc.get('id', '')}"
        if query in hay.lower():
            add_result("incident", inc, score=8)

    # Recommendations
    try:
        metadata = store.get_recommendation_metadata(limit=5000)
        for m in metadata:
            hay = f"{m.get('title', '')} {m.get('category', '')} {m.get('recommendation_id', '')}"
            if query in hay.lower():
                add_result("recommendation", m, score=7)
    except Exception:
        pass

    # Snapshots
    for snap in _load_all_snapshots(limit=50):
        ts_str = str(snap.get("timestamp", ""))
        run_ids = snap.get("recent_run_ids", [])
        if query in ts_str or any(query in str(r).lower() for r in run_ids):
            add_result("snapshot", snap, score=5)

    # Alerts
    try:
        for i in range(50):
            key = f"alert_tracker:alert-{i}"
            raw = store.get_metadata(key)
            if raw:
                ev = json.loads(raw) if isinstance(raw, str) else raw
                hay = f"{ev.get('type', '')} {ev.get('message', '')}"
                if query in hay.lower():
                    add_result("alert", ev, score=6)
    except Exception:
        pass

    # Inbox
    for item in _load_all_inbox_items():
        hay = f"{item.get('title', '')} {item.get('category', '')}"
        if query in hay.lower():
            add_result("inbox", item, score=6)

    results.sort(key=lambda x: -x.get("_score", 0))
    return {
        "query": q,
        "count": len(results),
        "results": results[:limit],
    }


# ------------------------------------------------------------------
# E2 — Investigation Replay
# ------------------------------------------------------------------

_INVESTIGATION_NAMESPACE = "operator:investigation"


def _investigation_key(inv_id: str) -> str:
    return f"{_INVESTIGATION_NAMESPACE}:{inv_id}"


def _load_all_investigations() -> List[Dict[str, Any]]:
    """Load investigation sessions from store metadata."""
    sessions: List[Dict[str, Any]] = []
    seen: set = set()
    try:
        for i in range(100):
            test_key = f"{_INVESTIGATION_NAMESPACE}:inv-{i}"
            raw = store.get_metadata(test_key)
            if raw:
                ev = json.loads(raw) if isinstance(raw, str) else raw
                sid = ev.get("id")
                if sid and sid not in seen:
                    seen.add(sid)
                    sessions.append(ev)
    except Exception:
        pass
    return sorted(sessions, key=lambda x: x.get("started_at", 0), reverse=True)


def _persist_investigation(inv: Dict[str, Any]) -> None:
    key = _investigation_key(inv["id"])
    try:
        if hasattr(store, "put_metadata"):
            store.put_metadata(key, inv)
        elif hasattr(store, "put_meta"):
            store.put_meta(key, json.dumps(inv))
    except Exception as exc:
        logger.warning("investigation persistence failed: %s", exc)


@router.post("/api/uar/investigations")
async def create_investigation(
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Start a new investigation session."""
    auth_middleware(credentials)
    import uuid

    inv_id = f"inv-{uuid.uuid4().hex[:8]}"
    now = int(time.time())
    inv = {
        "id": inv_id,
        "title": body.get("title", "Untitled Investigation"),
        "run_id": body.get("run_id"),
        "incident_id": body.get("incident_id"),
        "started_at": now,
        "ended_at": None,
        "actions": [],
        "status": "active",
    }
    _persist_investigation(inv)
    return inv


@router.get("/api/uar/investigations")
async def list_investigations(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List all investigation sessions."""
    auth_middleware(credentials)
    return _load_all_investigations()


@router.get("/api/uar/investigations/{inv_id}")
async def get_investigation(
    inv_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Get a single investigation session."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            return inv
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )


@router.post("/api/uar/investigations/{inv_id}/actions")
async def record_action(
    inv_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Record an operator action during an investigation."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            action = {
                "timestamp": int(time.time()),
                "type": body.get("type", "unknown"),
                "description": body.get("description", ""),
                "data": body.get("data"),
            }
            inv.setdefault("actions", []).append(action)
            inv["updated_at"] = int(time.time())
            _persist_investigation(inv)
            return action
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )


@router.put("/api/uar/investigations/{inv_id}")
async def update_investigation(
    inv_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """End or update an investigation session."""
    auth_middleware(credentials)
    for inv in _load_all_investigations():
        if inv.get("id") == inv_id:
            if "status" in body:
                inv["status"] = body["status"]
            if "ended_at" in body:
                inv["ended_at"] = body["ended_at"]
            inv["updated_at"] = int(time.time())
            _persist_investigation(inv)
            return inv
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Investigation not found",
    )


# ------------------------------------------------------------------
# E3 — Knowledge Graph Analytics
# ------------------------------------------------------------------


@router.get("/api/uar/graph-analytics/{center_id}")
async def get_graph_analytics(
    center_id: str,
    center_type: str = Query("run"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Compute analytics over the knowledge graph."""
    auth_middleware(credentials)

    analytics: Dict[str, Any] = {
        "center_id": center_id,
        "center_type": center_type,
        "generated_at": int(time.time()),
    }

    # Build graph for analysis
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen: set = set()

    def add_node(nid: str, ntype: str, label: str) -> None:
        if nid not in seen:
            seen.add(nid)
            nodes.append({"id": nid, "type": ntype, "label": label})

    def add_edge(src: str, tgt: str, etype: str) -> None:
        edges.append({"source": src, "target": tgt, "type": etype})

    add_node(center_id, center_type, center_id)

    if center_type == "run":
        run_id = center_id
        try:
            metadata = store.get_recommendation_metadata(limit=5000)
            for m in metadata:
                if m.get("run_id") == run_id:
                    rid = m["recommendation_id"]
                    add_node(rid, "recommendation", m.get("title", rid))
                    add_edge(run_id, rid, "has_recommendation")
        except Exception:
            pass

    for inc in _load_all_incidents():
        if center_id in inc.get("linked_run_ids", []):
            iid = inc["id"]
            add_node(iid, "incident", inc.get("title", iid))
            add_edge(center_id, iid, "has_incident")

    # Degree centrality (most connected)
    degree: Dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1

    most_connected = sorted(
        [{"id": k, "degree": v} for k, v in degree.items()],
        key=lambda x: -x["degree"],
    )[:5]

    # Common incident paths: run → recommendation → outcome
    paths: List[Dict[str, Any]] = []
    try:
        outcomes = store.get_outcomes(limit=5000)
        for o in outcomes:
            rid = o.get("recommendation_id")
            if rid and any(e["target"] == rid for e in edges):
                paths.append(
                    {
                        "run": center_id,
                        "recommendation": rid,
                        "outcome": o.get("outcome_type", "unknown"),
                    }
                )
    except Exception:
        pass

    # Trust cluster: group recommendations by trust band
    clusters: Dict[str, int] = {}
    try:
        from uar.core.trust_engine import compute_trust

        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        trust_result = compute_trust(outcomes, metadata)
        for t in trust_result.get("recommendation_types", []):
            score = t.get("trust_score", 0.0)
            if score >= 0.80:
                band = "highly_trusted"
            elif score >= 0.60:
                band = "trusted"
            elif score >= 0.40:
                band = "watch"
            elif score >= 0.20:
                band = "weak"
            else:
                band = "untrusted"
            clusters[band] = clusters.get(band, 0) + 1
    except Exception:
        pass

    # Resolution routes: recommendation_type → outcome_type frequency
    routes: Dict[str, Dict[str, int]] = {}
    try:
        outcomes = store.get_outcomes(limit=5000)
        metadata = store.get_recommendation_metadata(limit=5000)
        for o in outcomes:
            rid = o.get("recommendation_id")
            otype = o.get("outcome_type", "unknown")
            cat = next(
                (
                    m.get("category", "")
                    for m in metadata
                    if m.get("recommendation_id") == rid
                ),
                "",
            )
            if cat:
                if cat not in routes:
                    routes[cat] = {}
                routes[cat][otype] = routes[cat].get(otype, 0) + 1
    except Exception:
        pass

    analytics["node_count"] = len(nodes)
    analytics["edge_count"] = len(edges)
    analytics["most_connected"] = most_connected
    analytics["outcome_paths"] = paths[:10]
    analytics["trust_clusters"] = clusters
    analytics["resolution_routes"] = routes

    return analytics
