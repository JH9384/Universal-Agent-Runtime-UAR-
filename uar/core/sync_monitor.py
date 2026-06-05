"""Sync monitor for tracking and resyncing across UAR store backends.

Tracks write/read timestamps per store, computes sync lag, and provides
manual resync operations. Works with any RunStoreProtocol implementation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class StoreSyncStatus:
    """Per-store sync health snapshot."""

    store_id: str
    store_type: str  # json | sqlite | postgres | autonomi
    last_write_at: Optional[float] = None
    last_read_at: Optional[float] = None
    record_count: int = 0
    healthy: bool = True
    lag_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SyncHealthReport:
    """Aggregate sync health across all configured stores."""

    overall_healthy: bool = True
    stores: List[StoreSyncStatus] = field(default_factory=list)
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_healthy": self.overall_healthy,
            "stores": [s.to_dict() for s in self.stores],
            "checked_at": self.checked_at,
        }


class _StoreAdapter(Protocol):
    """Minimal interface the sync monitor needs from a store."""

    def list_records(
        self, user_id: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]: ...

    def put_metadata(self, key: str, value: Any) -> None: ...

    def get_metadata(self, key: str) -> Any: ...


class SyncMonitor:
    """Tracks sync health across one or more UAR stores.

    Usage:
        monitor = SyncMonitor()
        monitor.register_store("primary", get_store())
        monitor.register_store("replica", PostgresRunStore(db_url))
        report = monitor.check_health()
        monitor.resync("replica", source="primary")
    """

    _META_PREFIX = "uar:sync:"

    def __init__(self):
        self._stores: Dict[str, _StoreAdapter] = {}
        self._store_types: Dict[str, str] = {}

    def register_store(
        self,
        store_id: str,
        store: _StoreAdapter,
        store_type: str = "unknown",
    ) -> None:
        """Register a store for monitoring."""
        self._stores[store_id] = store
        self._store_types[store_id] = store_type
        logger.info(
            "Registered store %s (%s) for sync monitoring",
            store_id,
            store_type,
        )

    def deregister_store(self, store_id: str) -> None:
        """Remove a store from monitoring."""
        self._stores.pop(store_id, None)
        self._store_types.pop(store_id, None)

    def record_write(self, store_id: str) -> None:
        """Mark a write event on a store (call after append/flush)."""
        store = self._stores.get(store_id)
        if store is None:
            return
        ts = time.time()
        try:
            store.put_metadata(f"{self._META_PREFIX}last_write", ts)
        except Exception as exc:
            logger.warning(
                "Failed to record write timestamp for %s: %s", store_id, exc
            )

    def record_read(self, store_id: str) -> None:
        """Mark a read event on a store (call after list_records/get)."""
        store = self._stores.get(store_id)
        if store is None:
            return
        ts = time.time()
        try:
            store.put_metadata(f"{self._META_PREFIX}last_read", ts)
        except Exception as exc:
            logger.warning(
                "Failed to record read timestamp for %s: %s", store_id, exc
            )

    def check_health(self) -> SyncHealthReport:
        """Check sync health for all registered stores."""
        report = SyncHealthReport()
        now = time.time()
        max_write_ts: Optional[float] = None

        for store_id, store in self._stores.items():
            status = StoreSyncStatus(
                store_id=store_id,
                store_type=self._store_types.get(store_id, "unknown"),
            )
            try:
                records = store.list_records(limit=1)
                status.record_count = len(records)
                status.last_read_at = now

                # Retrieve persisted timestamps
                raw_write = store.get_metadata(
                    f"{self._META_PREFIX}last_write"
                )
                if raw_write:
                    status.last_write_at = float(raw_write)
                raw_read = store.get_metadata(f"{self._META_PREFIX}last_read")
                if raw_read:
                    status.last_read_at = float(raw_read)

                if status.last_write_at and max_write_ts:
                    status.lag_seconds = abs(
                        status.last_write_at - max_write_ts
                    )
                if max_write_ts is None or (
                    status.last_write_at
                    and status.last_write_at > max_write_ts
                ):
                    max_write_ts = status.last_write_at

            except Exception as exc:
                status.healthy = False
                status.error = str(exc)
                logger.warning(
                    "Sync health check failed for %s: %s",
                    store_id,
                    exc,
                )

            report.stores.append(status)
            if not status.healthy:
                report.overall_healthy = False

        report.checked_at = now
        return report

    def resync(
        self,
        target_id: str,
        source_id: Optional[str] = None,
        limit: int = 10000,
    ) -> Dict[str, Any]:
        """Manually resync a target store from a source store.

        If source_id is None, picks the store with the most recent write.
        Returns a result dict with copied_count and error if any.
        """
        target = self._stores.get(target_id)
        if target is None:
            return {
                "success": False,
                "error": f"Target store '{target_id}' not registered",
            }

        source_id = source_id or self._pick_latest_store()
        if source_id is None:
            return {"success": False, "error": "No source store available"}
        if source_id == target_id:
            return {
                "success": True,
                "copied": 0,
                "message": "Source and target are the same store",
            }

        source = self._stores.get(source_id)
        if source is None:
            return {
                "success": False,
                "error": f"Source store '{source_id}' not registered",
            }

        copied = 0
        try:
            records = source.list_records(limit=limit)
            for rec in records:
                try:
                    # Re-append via the target store's append if available;
                    # fallback to put_metadata for metadata-only stores.
                    if hasattr(target, "append"):
                        from uar.core.contracts import RunRecord

                        if isinstance(rec, dict):
                            target.append(RunRecord(**rec))
                        else:
                            target.append(rec)
                    copied += 1
                except Exception as exc:
                    logger.warning("Resync copy failed for record: %s", exc)

            self.record_write(target_id)
            logger.info(
                "Resynced %s records from %s to %s",
                copied,
                source_id,
                target_id,
            )
            return {
                "success": True,
                "copied": copied,
                "source": source_id,
                "target": target_id,
            }
        except Exception as exc:
            logger.exception(
                "Resync failed from %s to %s",
                source_id,
                target_id,
            )
            return {"success": False, "error": str(exc)}

    def _pick_latest_store(self) -> Optional[str]:
        """Return the store_id with the most recent last_write timestamp."""
        best_id: Optional[str] = None
        best_ts = 0.0
        for store_id, store in self._stores.items():
            try:
                raw = store.get_metadata(f"{self._META_PREFIX}last_write")
                if raw:
                    ts = float(raw)
                    if ts > best_ts:
                        best_ts = ts
                        best_id = store_id
            except Exception:
                continue
        return best_id


# Global singleton
_sync_monitor: Optional[SyncMonitor] = None


def get_sync_monitor() -> SyncMonitor:
    """Return the global SyncMonitor, lazily initialised."""
    global _sync_monitor
    if _sync_monitor is None:
        _sync_monitor = SyncMonitor()
    return _sync_monitor
