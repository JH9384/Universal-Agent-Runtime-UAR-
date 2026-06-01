"""Knowledge Graph Analytics router."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import _load_all_incidents
from uar.api.state import store

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


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

    degree: Dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1

    most_connected = sorted(
        [{"id": k, "degree": v} for k, v in degree.items()],
        key=lambda x: -x["degree"],
    )[:5]

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
