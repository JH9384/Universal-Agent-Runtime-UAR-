"""Caching for frequently accessed UOR objects.

Provides LRU caching with TTL support for UOR objects,
improving performance for frequently accessed content.
"""

import logging
import time
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cache entry with value and metadata."""

    value: Any
    timestamp: float = field(default_factory=time.time)
    hits: int = 0
    ttl: Optional[float] = None

    def is_expired(self) -> bool:
        """Check if entry is expired based on TTL."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def touch(self):
        """Update timestamp and increment hit count."""
        self.timestamp = time.time()
        self.hits += 1


class UORObjectCache:
    """LRU cache for UOR objects with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        """Initialize UOR object cache.

        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default time-to-live in seconds (None for no expiry)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key (typically object digest)

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check if expired
        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            logger.debug(f"Cache entry expired: {key}")
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        entry.touch()
        self.hits += 1

        logger.debug(f"Cache hit: {key} (hits: {entry.hits})")
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key (typically object digest)
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        # Evict if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_oldest()

        entry_ttl = ttl if ttl is not None else self.default_ttl
        entry = CacheEntry(value=value, ttl=entry_ttl)

        self.cache[key] = entry
        self.cache.move_to_end(key)
        logger.debug(f"Cache set: {key}")

    def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache delete: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        self.cache.clear()
        logger.info("Cache cleared")

    def _evict_oldest(self) -> None:
        """Evict the oldest (least recently used) entry."""
        if self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            logger.debug(f"Cache evicted: {oldest_key}")

    def cleanup_expired(self) -> int:
        """Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self.cache.items()
            if entry.is_expired()
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "default_ttl": self.default_ttl,
        }

    def get_keys(self) -> list[str]:
        """Get all cache keys.

        Returns:
            List of cache keys
        """
        return list(self.cache.keys())


class CachedObjectAccessor:
    """Wrapper for object access with caching."""

    def __init__(
        self,
        fetch_func: Callable[[str], Optional[Any]],
        cache: Optional[UORObjectCache] = None,
    ):
        """Initialize cached object accessor.

        Args:
            fetch_func: Function to fetch object when not in cache
            cache: Cache instance (creates default if None)
        """
        self.fetch_func = fetch_func
        self.cache = cache or UORObjectCache()

    def get(self, key: str) -> Optional[Any]:
        """Get object with caching.

        Args:
            key: Object key (typically digest)

        Returns:
            Object data from cache or fetched
        """
        # Try cache first
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Fetch from source
        obj = self.fetch_func(key)
        if obj is not None:
            self.cache.set(key, obj)

        return obj

    def invalidate(self, key: str) -> None:
        """Invalidate cached object.

        Args:
            key: Object key to invalidate
        """
        self.cache.delete(key)

    def prefetch(self, keys: list[str]) -> None:
        """Prefetch multiple objects into cache.

        Args:
            keys: List of object keys to prefetch
        """
        for key in keys:
            if key not in self.cache:
                obj = self.fetch_func(key)
                if obj is not None:
                    self.cache.set(key, obj)
