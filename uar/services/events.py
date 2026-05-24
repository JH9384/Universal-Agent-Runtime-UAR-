"""Event creation and formatting service — Single Source of Truth.

Eliminates the duplicated ``create_event()`` functions that existed in:
- ``server.py::stream_goal`` (SSE)
- ``server.py::stream_goal_ws`` (WebSocket /api/uar/stream/ws)
- ``server.py::websocket_run`` (WebSocket /ws/run)

All event creation goes through this service so schema changes happen
in one place.
"""

import importlib.util
import json
import time
import uuid
from typing import Any, Optional

from .base import BaseService

# Use orjson when available (10-100x faster than stdlib json)
_has_orjson = importlib.util.find_spec("orjson") is not None
if _has_orjson:
    import orjson  # type: ignore[import-untyped]

    def _dumps(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")
else:
    _dumps = json.dumps

# Optional msgpack for binary event encoding
_has_msgpack = importlib.util.find_spec("msgpack") is not None


class EventService(BaseService):
    """Create and format UAR events following the uar.event.v1 schema."""

    SCHEMA_VERSION = "uar.event.v1"

    def create(
        self,
        event_type: str,
        run_id: str,
        goal_id: str = "",
        skill: Optional[str] = None,
        payload: Optional[dict] = None,
        error: Optional[str] = None,
        correlation_id: str = "",
        **extra: Any,
    ) -> dict[str, Any]:
        """Create a single event dict following the canonical schema.

        Args:
            event_type: Event classification (e.g. ``skill_start``).
            run_id: Unique run identifier.
            goal_id: Associated goal identifier.
            skill: Skill name if skill-related.
            payload: Arbitrary event payload.
            error: Human-readable error string if applicable.
            correlation_id: Distributed tracing identifier.
            **extra: Additional fields merged into the event.

        Returns:
            Event dict conforming to ``uar.event.v1``.
        """
        cid = correlation_id or str(uuid.uuid4())
        event: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "type": event_type,
            "run_id": run_id,
            "goal_id": goal_id,
            "skill": skill,
            "timestamp": time.time(),
            "correlation_id": cid,
            "payload": payload or {},
            "error": error,
        }
        if extra:
            # Merge extra fields, but never overwrite canonical keys
            for key, value in extra.items():
                if key not in event:
                    event[key] = value
        return event

    def emit_sse(self, event: dict[str, Any]) -> str:
        """Format an event for Server-Sent Events (SSE).

        Uses orjson when available for fast serialization.
        Falls back to a safe JSON representation if the event contains
        unserializable values, ensuring the SSE stream never breaks.
        """
        try:
            payload = _dumps(event)
        except (TypeError, ValueError) as exc:
            self._log(
                "warning",
                f"Event contains unserializable data: {exc}. "
                f"Falling back to string repr.",
            )
            payload = json.dumps(event, default=str)
        return f"event: {event.get('type', 'unknown')}\ndata: {payload}\n\n"

    def pack(self, event: dict[str, Any]) -> bytes:
        """Serialize event to compact binary (msgpack or json bytes)."""
        if _has_msgpack:
            import msgpack  # type: ignore[import-untyped]

            return msgpack.packb(event, use_bin_type=True)
        return orjson.dumps(event) if _has_orjson else json.dumps(
            event, default=str
        ).encode("utf-8")

    def error(
        self,
        run_id: str,
        error_msg: str,
        code: str = "INTERNAL_ERROR",
        request_id: str = "",
        goal_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        """Create a standardised error event."""
        return self.create(
            event_type="error",
            run_id=run_id,
            goal_id=goal_id,
            correlation_id=correlation_id,
            error=error_msg,
            payload={
                "message": error_msg,
                "code": code,
                "request_id": request_id,
            },
        )

    def complete(
        self,
        run_id: str,
        status: str = "completed",
        errors: Optional[list[str]] = None,
        goal_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        """Create a standardised completion event."""
        return self.create(
            event_type="complete",
            run_id=run_id,
            goal_id=goal_id,
            correlation_id=correlation_id,
            payload={"status": status, "errors": errors or []},
        )

    def heartbeat(
        self,
        run_id: str,
        goal_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        """Create a standardised heartbeat event."""
        return self.create(
            event_type="heartbeat",
            run_id=run_id,
            goal_id=goal_id,
            correlation_id=correlation_id,
            payload={"timestamp": time.time()},
        )

    def orchestration_plan(
        self,
        graph: dict[str, Any],
        run_id: str = "pending",
        goal_id: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        """Create an orchestration plan event."""
        return self.create(
            event_type="orchestration_plan",
            run_id=run_id,
            goal_id=goal_id,
            correlation_id=correlation_id,
            payload={"graph": graph},
        )
