"""Activity log aggregator for operator-facing user activity & import history.

Queries run store metadata to produce a unified activity stream of:
- Run executions (created, completed, failed)
- Skill usage
- File imports
- Recommendation outcomes
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ActivityEvent:
    """A single activity log entry."""

    id: str
    event_type: str  # 'run', 'skill', 'import', 'outcome', 'feedback'
    actor: str  # user_id or 'system'
    target: str  # run_id, skill_name, file_name, rec_id
    action: str  # 'created', 'completed', 'failed', 'executed', 'imported'
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    """Aggregate activity events from the run store."""

    def __init__(self, store: _StoreAdapter):
        self._store = store

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

        # Sort by timestamp descending, apply type filter
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
