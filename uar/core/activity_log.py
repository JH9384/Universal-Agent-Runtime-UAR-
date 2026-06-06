"""Activity log aggregator for operator-facing user activity & import history.

Queries run store metadata to produce a unified activity stream of:
- Run executions (created, completed, failed)
- Skill usage
- File imports
- Recommendation outcomes

Events carry a UOR content digest for tamper detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ActivityEvent:
    """A single activity log entry with UOR content digest."""

    id: str
    event_type: str  # 'run', 'skill', 'import', 'outcome', 'feedback'
    actor: str  # user_id or 'system'
    target: str  # run_id, skill_name, file_name, rec_id
    action: str  # 'created', 'completed', 'failed', 'executed', 'imported'
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    uor_digest: Optional[str] = None  # computed on demand
    prev_hash: str = ""  # hash-chain link

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_digest(self) -> str:
        """UOR-ADDR-1 canonical digest of this event's content."""
        payload = {
            "id": self.id,
            "event_type": self.event_type,
            "actor": self.actor,
            "target": self.target,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
        }
        try:
            from uar.uor.bounded_json import compute_uor_digest

            return compute_uor_digest(payload)
        except Exception:
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()

    def compute_hash(self) -> str:
        """Legacy SHA-256 for hash-chain linkage."""
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class _StoreAdapter(Protocol):
    """Minimal interface needed from a store."""

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]: ...

    def get_outcomes(
        self,
        recommendation_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]: ...

    def get_feedback(
        self,
        recommendation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]: ...


class ActivityLogAggregator:
    """Aggregate activity events from the run store.

    Maintains a persistent hash chain across process restarts by
    storing the last event hash in a well-known file.
    """

    _CHAIN_FILE = ".uar_activity_chain"

    def __init__(self, store: _StoreAdapter):
        self._store = store

    def _load_last_hash(self) -> str:
        """Resume hash chain from persisted state."""
        try:
            import os
            path = os.path.join(os.getcwd(), self._CHAIN_FILE)
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return ""

    def _save_last_hash(self, last_hash: str) -> None:
        """Persist hash chain tail for next restart."""
        try:
            import os
            path = os.path.join(os.getcwd(), self._CHAIN_FILE)
            with open(path, "w") as f:
                f.write(last_hash)
        except Exception:
            pass

    def get_activity(
        self,
        limit: int = 200,
        event_types: Optional[List[str]] = None,
        since: Optional[float] = None,
    ) -> List[ActivityEvent]:
        """Build an activity stream from store data.

        Args:
            limit: Max events to return.
            event_types: Filter by type(s), or None for all.
            since: Unix timestamp — only events after this time.
        """
        events: List[ActivityEvent] = []
        cutoff = since or 0.0

        # 1. Run executions
        try:
            records = self._store.list_records(limit=limit)
            for rec in records:
                ts = rec.get("timestamp", 0)
                if isinstance(ts, (int, float)) and ts < cutoff:
                    continue
                status = rec.get("status", "unknown")
                events.append(
                    ActivityEvent(
                        id=f"run:{rec.get('run_id', 'unknown')}",
                        event_type="run",
                        actor=rec.get("user_id") or "system",
                        target=rec.get("run_id", ""),
                        action=status,
                        details={
                            "skills": rec.get("skills", []),
                            "errors": rec.get("errors", []),
                        },
                        timestamp=float(ts) if ts else time.time(),
                    )
                )
        except Exception as exc:
            logger.warning("Activity log: run query failed: %s", exc)

        # 2. Outcomes
        try:
            outcomes = self._store.get_outcomes(limit=limit)
            for o in outcomes:
                ts = o.get("timestamp", 0)
                if isinstance(ts, (int, float)) and ts < cutoff:
                    continue
                events.append(
                    ActivityEvent(
                        id=f"outcome:{o.get('recommendation_id', 'unknown')}",
                        event_type="outcome",
                        actor="system",
                        target=o.get("recommendation_id", ""),
                        action=o.get("outcome_type", "unknown"),
                        details={},
                        timestamp=float(ts) if ts else time.time(),
                    )
                )
        except Exception as exc:
            logger.warning("Activity log: outcome query failed: %s", exc)

        # 3. Feedback
        try:
            feedback = self._store.get_feedback(limit=limit)
            for f in feedback:
                ts = f.get("timestamp", 0)
                if isinstance(ts, (int, float)) and ts < cutoff:
                    continue
                events.append(
                    ActivityEvent(
                        id=f"feedback:{f.get('recommendation_id', 'unknown')}",
                        event_type="feedback",
                        actor=f.get("user_id") or "system",
                        target=f.get("recommendation_id", ""),
                        action=f.get("action", "unknown"),
                        details={},
                        timestamp=float(ts) if ts else time.time(),
                    )
                )
        except Exception as exc:
            logger.warning("Activity log: feedback query failed: %s", exc)

        # Sort by timestamp ascending for hash chain, then reverse
        events.sort(key=lambda e: e.timestamp)

        prev_hash = self._load_last_hash()
        for ev in events:
            ev.prev_hash = prev_hash
            ev.uor_digest = ev.compute_digest()
            prev_hash = ev.compute_hash()

        # Persist the chain tail for next restart
        if prev_hash:
            self._save_last_hash(prev_hash)

        events.sort(key=lambda e: e.timestamp, reverse=True)
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        return events[:limit]


# Global singleton
_aggregator: Optional[ActivityLogAggregator] = None


def get_activity_log_aggregator(
    store: Optional[_StoreAdapter] = None,
) -> ActivityLogAggregator:
    """Return the global ActivityLogAggregator, lazily initialised."""
    global _aggregator
    if _aggregator is None:
        if store is None:
            from uar.container import get_container

            store = get_container().get_store()
        _aggregator = ActivityLogAggregator(store)
    return _aggregator
