"""Per-skill result cache with SHA-256 keyed storage.

Wraps any skill function to cache its result keyed by:
- skill name
- serialized goal metadata
- a configurable TTL

Usage:
    from uar.core.skill_cache import cached_skill

    @cached_skill(ttl_seconds=300)
    @register_skill("math_compute")
    def math_compute(ctx):
        ...
"""

import functools
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class SkillCache:
    """In-memory LRU cache for skill results.

    Thread-safe.  Results are keyed by SHA-256 of the serialized
    (skill_name, metadata) tuple.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._maxsize = maxsize

    def _make_key(self, skill_name: str, metadata: Dict[str, Any]) -> str:
        """Deterministic SHA-256 key from skill + metadata."""
        payload = json.dumps(
            {"skill": skill_name, "metadata": metadata},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(
        self, skill_name: str, metadata: Dict[str, Any]
    ) -> Optional[Any]:
        """Return cached result or ``None`` if expired / missing."""
        key = self._make_key(skill_name, metadata)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry["expires"] < time.time():
                del self._store[key]
                return None
            logger.debug(f"Cache hit: {skill_name} ({key[:8]}...)")
            return entry["value"]

    def set(
        self,
        skill_name: str,
        metadata: Dict[str, Any],
        value: Any,
        ttl_seconds: float,
    ) -> None:
        """Store a result with the given TTL."""
        key = self._make_key(skill_name, metadata)
        with self._lock:
            # Simple eviction: if over maxsize, drop oldest half
            if len(self._store) >= self._maxsize:
                sorted_keys = sorted(
                    self._store,
                    key=lambda k: self._store[k]["expires"],
                )
                for old in sorted_keys[: len(sorted_keys) // 2]:
                    del self._store[old]

            self._store[key] = {
                "value": value,
                "expires": time.time() + ttl_seconds,
                "skill": skill_name,
            }
            logger.debug(f"Cache set: {skill_name} ({key[:8]}...)")

    def invalidate(
        self, skill_name: Optional[str] = None
    ) -> int:
        """Remove entries. If skill_name given, only remove for that skill."""
        with self._lock:
            if skill_name is None:
                count = len(self._store)
                self._store.clear()
                return count
            to_remove = [
                k for k, v in self._store.items() if v["skill"] == skill_name
            ]
            for k in to_remove:
                del self._store[k]
            return len(to_remove)

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            return {
                "size": len(self._store),
                "maxsize": self._maxsize,
                "skills": sorted({v["skill"] for v in self._store.values()}),
            }


# Global shared cache instance
_global_skill_cache: Optional[SkillCache] = None
_global_cache_lock = threading.Lock()


def get_skill_cache(maxsize: int = 1024) -> SkillCache:
    """Get or create the global skill cache."""
    global _global_skill_cache
    with _global_cache_lock:
        if _global_skill_cache is None:
            _global_skill_cache = SkillCache(maxsize=maxsize)
        return _global_skill_cache


def cached_skill(
    *,
    ttl_seconds: float = 300.0,
    maxsize: int = 1024,
    skip_on_error: bool = True,
) -> Callable[[Callable], Callable]:
    """Decorator that caches a skill's result.

    Args:
        ttl_seconds: Time-to-live for cached entries.
        maxsize: Maximum number of entries in the cache.
        skip_on_error: If ``True``, do not cache results whose
            ``status`` field equals ``"failed"``.
    """

    def decorator(fn: Callable) -> Callable:
        cache = get_skill_cache(maxsize=maxsize)

        @functools.wraps(fn)
        def wrapper(ctx: Any) -> Any:
            metadata = getattr(ctx, "goal", {}).get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            # Try cache read
            cached = cache.get(fn.__name__, metadata)
            if cached is not None:
                return cached

            # Execute
            result = fn(ctx)

            # Store if not an error (and result is a dict)
            if isinstance(result, dict):
                if skip_on_error and result.get("status") == "failed":
                    pass
                else:
                    cache.set(fn.__name__, metadata, result, ttl_seconds)

            return result

        # Attach cache control methods
        _fn_name = fn.__name__
        wrapper.cache_invalidate = (  # type: ignore
            lambda: cache.invalidate(_fn_name)
        )
        wrapper.cache_stats = lambda: cache.stats()  # type: ignore
        return wrapper

    return decorator
