"""Alert Accuracy Tracker — track fired / acted / ignored webhook alerts.

Stores alert events in SQLite metadata and provides accuracy metrics.

Usage:
    from uar.api.alert_tracker import alert_tracker
    alert_tracker.record_fired(alert_id, alert_type, severity, message)
    alert_tracker.record_action(alert_id, "acted")  # or "ignored"
    metrics = alert_tracker.get_accuracy_metrics(hours=168)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

_ALERT_NAMESPACE = "alert_tracker"


class AlertTracker:
    """Lightweight alert accuracy tracker backed by store metadata."""

    def __init__(self, store: Optional[Any] = None) -> None:
        self._store = store
        self._pending: List[Dict[str, Any]] = []

    def bind_store(self, store: Any) -> None:
        """Bind to a store that supports put_meta/get_metadata."""
        self._store = store

    def record_fired(
        self,
        alert_type: str,
        severity: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record that an alert was fired. Returns alert ID."""
        alert_id = f"alert-{int(time.time() * 1000)}-{alert_type}"
        event = {
            "id": alert_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "data": data or {},
            "fired_at": time.time(),
            "status": "fired",
        }
        self._persist_event(event)
        return alert_id

    def record_action(self, alert_id: str, status: str) -> bool:
        """Mark an alert as 'acted' or 'ignored'."""
        if status not in ("acted", "ignored"):
            return False
        event = self._load_event(alert_id)
        if event is None:
            return False
        event["status"] = status
        event["resolved_at"] = time.time()
        self._persist_event(event)
        return True

    def get_accuracy_metrics(self, hours: int = 168) -> Dict[str, Any]:
        """Return accuracy metrics for alerts in the last N hours."""
        cutoff = time.time() - (hours * 3600)
        events = self._load_all_events()
        recent = [e for e in events if e.get("fired_at", 0) >= cutoff]

        fired = len(recent)
        acted = sum(1 for e in recent if e.get("status") == "acted")
        ignored = sum(1 for e in recent if e.get("status") == "ignored")
        unresolved = sum(1 for e in recent if e.get("status") == "fired")

        by_type: Dict[str, Dict[str, int]] = {}
        for e in recent:
            at = e.get("alert_type", "unknown")
            if at not in by_type:
                by_type[at] = {"fired": 0, "acted": 0, "ignored": 0}
            by_type[at]["fired"] += 1
            if e.get("status") == "acted":
                by_type[at]["acted"] += 1
            elif e.get("status") == "ignored":
                by_type[at]["ignored"] += 1

        # Latency: time from fired to resolved (for acted/ignored)
        latencies = []
        for e in recent:
            if e.get("status") in ("acted", "ignored"):
                fired_at = e.get("fired_at", 0)
                resolved_at = e.get("resolved_at", fired_at)
                latencies.append(resolved_at - fired_at)

        return {
            "generated_at": time.time(),
            "hours": hours,
            "total_fired": fired,
            "acted": acted,
            "ignored": ignored,
            "unresolved": unresolved,
            "action_rate": round(acted / max(fired, 1), 3),
            "ignore_rate": round(ignored / max(fired, 1), 3),
            "unresolved_rate": round(unresolved / max(fired, 1), 3),
            "avg_resolution_seconds": (
                round(sum(latencies) / len(latencies), 1)
                if latencies else None
            ),
            "by_type": by_type,
        }

    def _persist_event(self, event: Dict[str, Any]) -> None:
        """Write event to store metadata."""
        key = f"{_ALERT_NAMESPACE}:{event['id']}"
        if self._store is not None:
            try:
                if hasattr(self._store, "put_metadata"):
                    import json
                    self._store.put_metadata(key, json.dumps(event))
                elif hasattr(self._store, "put_meta"):
                    import json
                    self._store.put_meta(key, json.dumps(event))
            except Exception:
                pass
        # Always keep in memory: acts as fallback when the store lacks
        # list_meta_keys and as a cache for in-process reads.
        self._pending = [
            e for e in self._pending if e["id"] != event["id"]
        ]
        self._pending.append(event)

    def _load_event(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Load a single event by ID."""
        key = f"{_ALERT_NAMESPACE}:{alert_id}"
        if self._store is not None:
            try:
                if hasattr(self._store, "get_metadata"):
                    import json
                    raw = self._store.get_metadata(key)
                    if raw:
                        return json.loads(raw)
            except Exception:
                pass
        for e in self._pending:
            if e["id"] == alert_id:
                return e
        return None

    def _load_all_events(self) -> List[Dict[str, Any]]:
        """Load all alert events."""
        events: List[Dict[str, Any]] = []
        seen: set[str] = set()
        if self._store is not None:
            try:
                if hasattr(self._store, "list_meta_keys"):
                    import json
                    keys = self._store.list_meta_keys()
                    for key in keys:
                        if key.startswith(f"{_ALERT_NAMESPACE}:"):
                            raw = self._store.get_metadata(key)
                            if raw:
                                try:
                                    ev = json.loads(raw)
                                    ev_id = ev.get("id")
                                    if ev_id and ev_id not in seen:
                                        seen.add(ev_id)
                                        events.append(ev)
                                except Exception:
                                    pass
            except Exception:
                pass
        for e in self._pending:
            e_id = e.get("id")
            if e_id and e_id not in seen:
                seen.add(e_id)
                events.append(e)
        return events


# Global instance
_alert_tracker: Optional[AlertTracker] = None


def get_alert_tracker(store: Optional[Any] = None) -> AlertTracker:
    """Get or create the global alert tracker."""
    global _alert_tracker
    if _alert_tracker is None:
        _alert_tracker = AlertTracker(store)
    elif store is not None and _alert_tracker._store is None:
        _alert_tracker.bind_store(store)
    return _alert_tracker


def alert_tracker() -> AlertTracker:
    """Return the global alert tracker (may be unbound)."""
    return get_alert_tracker()
