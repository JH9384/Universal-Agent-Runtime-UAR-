"""Shared helpers for operator workflow routers.

Auth and audit helpers are delegated to ``helpers.auth``; entity
CRUD helpers are delegated to ``helpers.entity_store``.  This file
retains the public function signatures so all 21 router imports stay
unchanged.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from uar.api.middleware import auth_middleware  # noqa: F401
from uar.api.state import store
from uar.api.routers.operator.helpers.auth import (  # noqa: F401
    audit_admin_action,
    require_operator,
)
from uar.api.routers.operator.helpers.entity_store import (
    MetadataEntityStore,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Entity stores
# ------------------------------------------------------------------

_incident_store = MetadataEntityStore(
    "operator:incident",
    id_field="id",
    sort_field="created_at",
    max_index_scan=100,
    use_list_meta_keys=True,
)
_snapshot_store = MetadataEntityStore(
    "operator:snapshot",
    id_field="timestamp",
    sort_field="timestamp",
    max_index_scan=100,
    use_list_meta_keys=False,
)
_inbox_store = MetadataEntityStore(
    "operator:inbox",
    id_field="id",
    sort_field="created_at",
    max_index_scan=200,
    use_list_meta_keys=False,
)
_investigation_store = MetadataEntityStore(
    "operator:investigation",
    id_field="id",
    sort_field="started_at",
    max_index_scan=100,
    use_list_meta_keys=False,
)


# ------------------------------------------------------------------
# Incident helpers (delegated to _incident_store)
# ------------------------------------------------------------------


def _incident_key(incident_id: str) -> str:
    return _incident_store.key(incident_id)


def _load_all_incidents() -> List[Dict[str, Any]]:
    return _incident_store.load_all()


def _persist_incident(incident: Dict[str, Any]) -> None:
    _incident_store.persist(incident)


# ------------------------------------------------------------------
# Snapshot helpers (delegated to _snapshot_store)
# ------------------------------------------------------------------


def _snapshot_key(timestamp: int) -> str:
    return _snapshot_store.key(str(timestamp))


def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    _snapshot_store.persist(snapshot)


def _get_snapshot_for_day(day_timestamp: int) -> Optional[Dict[str, Any]]:
    """Find closest snapshot to a given day."""
    try:
        for hour in range(24):
            ts = (day_timestamp // 86400) * 86400 + hour * 3600
            key = _snapshot_key(ts)
            raw = store.get_metadata(key)
            if raw:
                return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as _exc:
        logger.warning("Snapshot lookup failed: %s", _exc)
    return None


def _load_all_snapshots(limit: int = 100) -> List[Dict[str, Any]]:
    """Load recent snapshots."""
    snapshots = _snapshot_store.load_all()
    if limit:
        snapshots = snapshots[:limit]
    return snapshots


# ------------------------------------------------------------------
# Inbox helpers (delegated to _inbox_store)
# ------------------------------------------------------------------


def _inbox_key(item_id: str) -> str:
    return _inbox_store.key(item_id)


def _load_all_inbox_items() -> List[Dict[str, Any]]:
    return _inbox_store.load_all()


def _persist_inbox_item(item: Dict[str, Any]) -> None:
    _inbox_store.persist(item)


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


# ------------------------------------------------------------------
# Investigation helpers (delegated to _investigation_store)
# ------------------------------------------------------------------


def _investigation_key(inv_id: str) -> str:
    return _investigation_store.key(inv_id)


def _load_all_investigations() -> List[Dict[str, Any]]:
    return _investigation_store.load_all()


def _persist_investigation(inv: Dict[str, Any]) -> None:
    _investigation_store.persist(inv)
