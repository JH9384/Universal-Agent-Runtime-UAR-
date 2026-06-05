"""Maintenance window system for UAR.

Allows operators to schedule planned downtime windows during which
new runs are rejected with a clear error message.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceWindow:
    """A single scheduled maintenance window."""

    id: str
    start_at: float
    end_at: float
    description: str = ""
    created_by: str = "system"
    created_at: float = field(default_factory=time.time)

    def is_active(self, now: Optional[float] = None) -> bool:
        ts = now if now is not None else time.time()
        return self.start_at <= ts <= self.end_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class _StoreAdapter(Protocol):
    """Minimal interface needed from a store."""

    def put_metadata(self, key: str, value: Any) -> None: ...

    def get_metadata(self, key: str) -> Any: ...

    def list_meta_keys(self) -> List[str]: ...


class MaintenanceManager:
    """Manage maintenance windows backed by store metadata."""

    _META_PREFIX = "uar:maintenance:"

    def __init__(self, store: _StoreAdapter):
        self._store = store

    def _key(self, wid: str) -> str:
        return f"{self._META_PREFIX}{wid}"

    def list_windows(self) -> List[MaintenanceWindow]:
        """Return all stored windows, sorted by start time."""
        windows: List[MaintenanceWindow] = []
        try:
            keys = self._store.list_meta_keys()
        except Exception:
            keys = [f"{self._META_PREFIX}{i}" for i in range(50)]
        for key in keys:
            if not key.startswith(self._META_PREFIX):
                continue
            try:
                raw = self._store.get_metadata(key)
                if not raw:
                    continue
                import json

                data = json.loads(raw) if isinstance(raw, str) else raw
                windows.append(MaintenanceWindow(**data))
            except Exception as exc:
                logger.debug("Skipping corrupt window %s: %s", key, exc)
        return sorted(windows, key=lambda w: w.start_at)

    def get_active_window(
        self, now: Optional[float] = None
    ) -> Optional[MaintenanceWindow]:
        """Return the currently active maintenance window, if any."""
        for w in self.list_windows():
            if w.is_active(now):
                return w
        return None

    def schedule(
        self,
        wid: str,
        start_at: float,
        end_at: float,
        description: str = "",
        created_by: str = "system",
    ) -> MaintenanceWindow:
        """Create or update a maintenance window."""
        if end_at <= start_at:
            raise ValueError("end_at must be after start_at")
        window = MaintenanceWindow(
            id=wid,
            start_at=start_at,
            end_at=end_at,
            description=description,
            created_by=created_by,
            created_at=time.time(),
        )
        import json

        self._store.put_metadata(
            self._key(wid), json.dumps(asdict(window))
        )
        logger.info(
            "Scheduled maintenance window %s (%s - %s)", wid, start_at, end_at
        )
        return window

    def cancel(self, wid: str) -> bool:
        """Cancel a maintenance window. Returns True if existed."""
        try:
            raw = self._store.get_metadata(self._key(wid))
            if raw:
                self._store.put_metadata(self._key(wid), "")
                logger.info("Cancelled maintenance window %s", wid)
                return True
        except Exception as exc:
            logger.warning("Failed to cancel window %s: %s", wid, exc)
        return False

    def check_blocked(
        self, now: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Return block info if a window is active, else None."""
        active = self.get_active_window(now)
        if active is None:
            return None
        return {
            "blocked": True,
            "window_id": active.id,
            "description": active.description,
            "ends_at": active.end_at,
            "message": (
                f"Maintenance in progress: {active.description}. "
                f"Estimated end: {time.ctime(active.end_at)}"
            ),
        }


# Global singleton
_manager: Optional[MaintenanceManager] = None


def get_maintenance_manager(
    store: Optional[_StoreAdapter] = None,
) -> MaintenanceManager:
    """Return the global MaintenanceManager, lazily initialised."""
    global _manager
    if _manager is None:
        if store is None:
            from uar.api.state import store as _store

            store = _store
        _manager = MaintenanceManager(store)
    return _manager
