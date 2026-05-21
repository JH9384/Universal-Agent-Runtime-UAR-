"""Result caching system to avoid redundant computations.

This module provides a caching layer for skill execution results,
allowing the system to reuse previously computed results when
the same inputs are provided.
"""

import os
import threading
from typing import Optional

from .cache_backends import AutoCacheBackend

# Legacy alias for backward compatibility
ResultCache = AutoCacheBackend


# Global cache instance
_global_cache: Optional[ResultCache] = None
_global_cache_lock = threading.Lock()


def get_cache() -> ResultCache:
    """Get the global cache instance (thread-safe singleton).

    Returns:
        Global ResultCache instance
    """
    global _global_cache
    if _global_cache is None:
        with _global_cache_lock:
            # Double-check after acquiring lock
            if _global_cache is None:
                cache_dir = os.getenv("UAR_CACHE_DIR")
                try:
                    ttl = int(os.getenv("UAR_CACHE_TTL", "3600"))
                except (ValueError, TypeError):
                    ttl = 3600
                try:
                    max_entries = int(
                        os.getenv("UAR_CACHE_MAX_ENTRIES", "1000")
                    )
                except (ValueError, TypeError):
                    max_entries = 1000
                try:
                    max_size = int(
                        os.getenv("UAR_CACHE_MAX_SIZE", str(100 * 1024 * 1024))
                    )
                except (ValueError, TypeError):
                    max_size = 100 * 1024 * 1024
                _global_cache = ResultCache(
                    cache_dir=cache_dir,
                    ttl_seconds=ttl,
                    max_entries=max_entries,
                    max_size_bytes=max_size,
                )
    return _global_cache


def clear_global_cache(skill_name: Optional[str] = None) -> None:
    """Clear the global cache.

    Args:
        skill_name: If provided, only clear entries for this skill
    """
    cache = get_cache()
    cache.clear(skill_name=skill_name)
