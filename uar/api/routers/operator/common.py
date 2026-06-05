"""Shared helpers for operator workflow routers."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import auth_middleware
from uar.api.state import store
from uar.core.audit import get_audit_logger

logger = logging.getLogger(__name__)

# Operator/admin tiers that may perform destructive admin actions
_ADMIN_TIERS = frozenset({"operator", "admin", "developer"})


def require_operator(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[Dict[str, Any]]:
    """Authenticate and require operator-or-higher tier.

    Returns user_info dict on success, raises 403 on insufficient tier.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        # Anonymous — not allowed for admin endpoints
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
                "message": "Admin endpoints require a valid API key.",
            },
        )
    tier = user_info.get("tier", "")
    if tier not in _ADMIN_TIERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Insufficient privileges",
                "error_code": "FORBIDDEN",
                "message": (
                    f"Tier '{tier}' is not authorised for admin operations."
                ),
            },
        )
    return user_info


def audit_admin_action(
    *,
    user_info: Optional[Dict[str, Any]],
    action: str,
    resource: str,
    outcome: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """Write an immutable audit record for an admin action.

    Also fires webhook alerts for critical outcomes (failure,
    auth denial, deletion) so on-call engineers are paged.

    Non-blocking: exceptions are swallowed so the main operation
    is never impeded by audit-log I/O or webhook delivery.
    """
    try:
        actor = (
            user_info.get("user", "unknown")
            if user_info
            else "unknown"
        )
        get_audit_logger().write(
            event_type="admin_action",
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            details=details,
            request_id=request_id,
        )
    except Exception:
        pass

    # Fire webhook for critical events
    try:
        if outcome in ("failure", "denied", "not_found") or \
                "DELETE" in action:
            from uar.api.webhook_alerts import get_webhook_alerter

            alerter = get_webhook_alerter()
            alerter.alert_admin_action(
                actor=actor,
                action=action,
                resource=resource,
                outcome=outcome,
                details=details,
            )
    except Exception:
        pass


# Namespaces
_INCIDENT_NAMESPACE = "operator:incident"
_SNAPSHOT_NAMESPACE = "operator:snapshot"
_INBOX_NAMESPACE = "operator:inbox"
_INVESTIGATION_NAMESPACE = "operator:investigation"

# ------------------------------------------------------------------
# Incident helpers
# ------------------------------------------------------------------


def _incident_key(incident_id: str) -> str:
    return f"{_INCIDENT_NAMESPACE}:{incident_id}"


def _load_all_incidents() -> List[Dict[str, Any]]:
    """Load incidents from store metadata (with in-memory fallback)."""
    incidents: List[Dict[str, Any]] = []
    seen: set = set()
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
        except Exception as _exc:
            logger.warning("Incident list_meta_keys failed: %s", _exc)
    try:
        for i in range(100):
            test_key = f"{_INCIDENT_NAMESPACE}:incident-{i}"
            raw = store.get_metadata(test_key)
            if raw:
                try:
                    ev = json.loads(raw) if isinstance(raw, str) else raw
                except Exception as _exc:
                    logger.debug("Corrupt incident JSON: %s", _exc)
                    continue
                iid = ev.get("id")
                if iid and iid not in seen:
                    seen.add(iid)
                    incidents.append(ev)
    except Exception as _exc:
        logger.warning("Incident metadata scan failed: %s", _exc)
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


# ------------------------------------------------------------------
# Snapshot helpers
# ------------------------------------------------------------------


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
    snapshots: List[Dict[str, Any]] = []
    seen: set = set()
    now = int(time.time())
    for h in range(limit):
        ts = now - h * 3600
        try:
            key = _snapshot_key(ts)
            raw = store.get_metadata(key)
            if raw:
                try:
                    snap = json.loads(raw) if isinstance(raw, str) else raw
                except Exception as _exc:
                    logger.debug("Corrupt snapshot JSON: %s", _exc)
                    continue
                ts_val = snap.get("timestamp")
                if ts_val and ts_val not in seen:
                    seen.add(ts_val)
                    snapshots.append(snap)
        except Exception as _exc:
            logger.warning("Snapshot metadata scan failed: %s", _exc)
            break
    return sorted(snapshots, key=lambda x: x.get("timestamp", 0), reverse=True)


# ------------------------------------------------------------------
# Inbox helpers
# ------------------------------------------------------------------


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
                try:
                    ev = json.loads(raw) if isinstance(raw, str) else raw
                except Exception as _exc:
                    logger.debug("Corrupt inbox JSON: %s", _exc)
                    continue
                iid = ev.get("id")
                if iid and iid not in seen:
                    seen.add(iid)
                    items.append(ev)
    except Exception as _exc:
        logger.warning("Inbox metadata scan failed: %s", _exc)
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


# ------------------------------------------------------------------
# Investigation helpers
# ------------------------------------------------------------------


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
                try:
                    ev = json.loads(raw) if isinstance(raw, str) else raw
                except Exception as _exc:
                    logger.debug("Corrupt investigation JSON: %s", _exc)
                    continue
                sid = ev.get("id")
                if sid and sid not in seen:
                    seen.add(sid)
                    sessions.append(ev)
    except Exception as _exc:
        logger.warning("Investigation metadata scan failed: %s", _exc)
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
