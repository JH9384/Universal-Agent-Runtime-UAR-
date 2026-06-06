"""Materialized analytics cache for UAR.

D4A-1 — Operational Optimization
Reduces aggregate endpoint latency by caching pre-computed analytics
snapshots in memory. Cache invalidates automatically on new runs
or burn-in execution.

Architecture:
    Run Store
        ↓
    AnalyticsCache (in-memory, TTL 60s)
        ↓
    Panels
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_MAX_ANALYTICS_CACHE_SIZE = max(
    1,
    int(
        os.getenv("UAR_ANALYTICS_CACHE_SIZE", "256").strip()
        or "256"
    ),
)


@dataclass
class _CacheEntry:
    """Single cached analytics snapshot."""

    payload: dict
    generated_at: float
    ttl_seconds: float = 60.0
    payload_digest: Optional[str] = None


class AnalyticsCache:
    """In-memory TTL cache for analytics endpoint payloads.

    Thread-safe. Keys are scoped by endpoint, user, admin flag,
    hours window, and record limit so that different callers do not
    collide.
    """

    def __init__(
        self,
        ttl_seconds: float = 60.0,
        max_size: int = _MAX_ANALYTICS_CACHE_SIZE,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(
        endpoint: str,
        user: Optional[str],
        is_admin: bool,
        hours: int,
        limit: int,
    ) -> str:
        return f"{endpoint}:{user}:{is_admin}:{hours}:{limit}"

    @staticmethod
    def _compute_digest(payload: dict) -> Optional[str]:
        """UOR-ADDR-1 digest of payload for integrity verification."""
        try:
            from uar.uor.bounded_json import compute_uor_digest

            return compute_uor_digest(payload)
        except Exception:
            return None

    def get(
        self,
        endpoint: str,
        user: Optional[str],
        is_admin: bool,
        hours: int,
        limit: int,
    ) -> Optional[dict]:
        """Return cached payload if present, not expired, and intact."""
        key = self._key(endpoint, user, is_admin, hours, limit)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() - entry.generated_at > entry.ttl_seconds:
                del self._store[key]
                return None
            # Integrity check: if digest is stored, verify it matches
            if entry.payload_digest is not None:
                current = self._compute_digest(entry.payload)
                if current != entry.payload_digest:
                    logger.warning(
                        "Analytics cache integrity failure for %s "
                        "(expected %s, got %s). Treating as miss.",
                        key,
                        entry.payload_digest,
                        current,
                    )
                    del self._store[key]
                    return None
            return entry.payload

    def set(
        self,
        endpoint: str,
        user: Optional[str],
        is_admin: bool,
        hours: int,
        limit: int,
        payload: dict,
    ) -> None:
        """Store payload in cache with integrity digest."""
        key = self._key(endpoint, user, is_admin, hours, limit)
        digest = self._compute_digest(payload)
        with self._lock:
            # Evict oldest entries if at capacity
            while len(self._store) >= self._max_size:
                oldest = next(iter(self._store))
                del self._store[oldest]
            self._store[key] = _CacheEntry(
                payload=payload,
                generated_at=time.time(),
                ttl_seconds=self._ttl,
                payload_digest=digest,
            )

    def invalidate(self, endpoint: Optional[str] = None) -> None:
        """Invalidate cache entries.

        If *endpoint* is None, all entries are removed.
        If *endpoint* is given, only keys for that endpoint
        are removed.
        """
        with self._lock:
            if endpoint is None:
                count = len(self._store)
                self._store.clear()
                logger.info(
                    "Analytics cache invalidated (all): %d entries", count
                )
            else:
                prefix = f"{endpoint}:"
                keys = [k for k in self._store if k.startswith(prefix)]
                for k in keys:
                    del self._store[k]
                logger.info(
                    "Analytics cache invalidated (%s): %d entries",
                    endpoint,
                    len(keys),
                )

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            return {
                "entries": len(self._store),
                "ttl_seconds": self._ttl,
            }


# Global singleton used by all analytics endpoints.
ANALYTICS_CACHE = AnalyticsCache(ttl_seconds=60.0)
