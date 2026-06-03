"""Knowledge Graph router (v1 + v2)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _load_all_incidents,
    _load_all_snapshots,
)
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


def _check_run_access(store, run_id: str, user: str, is_admin: bool) -> bool:
    """Return True if user may access run_id."""
    if is_admin:
        return True
    rec = store.get_by_run_id(run_id)
    if rec is None:
        return False
    owner = rec.get("user_id") or rec.get("user", "")
    return not owner or owner == user


@router.get("/api/uar/graph/{run_id}")
async def get_knowledge_graph(
    run_id: str,
    depth: int = 2,  # type: ignore[assignment]
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return a knowledge graph centered on a run."""
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    if not _check_run_access(store, run_id, user or "", is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    def _build_graph(run_id: str, depth: int):
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen: set = set()

        nodes.append({"id": run_id, "type": "run", "label": run_id})
        seen.add(run_id)

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
                        {"id": goal_id, "type": "goal", "label": goal_id}
                    )
                    seen.add(goal_id)
                    edges.append(
                        {
                            "source": run_id,
                            "target": goal_id,
                            "type": "has_goal",
                        }
                    )
        except Exception:
            pass

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

    return await run_in_threadpool(_build_graph, run_id, depth)


@router.get("/api/uar/graph-v2/{center_id}")
async def get_knowledge_graph_v2(
    center_id: str,
    center_type: str = "run",  # type: ignore[assignment]
    depth: int = 2,  # type: ignore[assignment]
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Expanded knowledge graph with operator, alert, snapshot nodes."""
    user_info = auth_middleware(credentials)
    user = user_info.get("user") if user_info else None
    is_admin = user_info.get("tier") == "admin" if user_info else False

    if center_type == "run" and not _check_run_access(
        store, center_id, user or "", is_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )

    def _build_graph_v2(center_id: str, center_type: str, depth: int):
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen: set = set()

        def add_node(
            node_id: str, ntype: str, label: str, **extra: Any
        ) -> None:
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

        try:
            for snap in _load_all_snapshots(limit=50):
                if center_id in snap.get("recent_run_ids", []):
                    sid = f"snap:{snap['timestamp']}"
                    add_node(sid, "snapshot", f"Snap {snap['timestamp']}")
                    add_edge(center_id, sid, "has_snapshot")
        except Exception:
            pass

        for inc in _load_all_incidents():
            if center_id in (inc.get("linked_run_ids", []) + [center_id]):
                assignee = inc.get("assigned_to") or inc.get("operator")
                if assignee:
                    oid = f"op:{assignee}"
                    add_node(oid, "operator", assignee)
                    add_edge(inc["id"], oid, "assigned_to")

        return {"nodes": nodes, "edges": edges}

    return await run_in_threadpool(
        _build_graph_v2, center_id, center_type, depth
    )
