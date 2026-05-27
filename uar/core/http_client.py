"""Shared HTTP client with per-domain connection pools,
circuit breaker integration, and exponential backoff retry.
"""

import asyncio
import logging
import os
import random
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from uar.core.async_utils import run_sync_safe

logger = logging.getLogger(__name__)

# Per-domain aiohttp session cache
_sessions: Dict[str, Any] = {}
_session_lock = asyncio.Lock()

# Retry configuration
_MAX_RETRIES = max(
    0, min(10, int(os.getenv("UAR_HTTP_MAX_RETRIES", "3").strip() or "3"))
)
_BASE_DELAY = max(
    0.0,
    min(5.0, float(os.getenv("UAR_HTTP_BASE_DELAY", "0.5").strip() or "0.5")),
)
_MAX_DELAY = max(
    0.0,
    min(60.0, float(os.getenv("UAR_HTTP_MAX_DELAY", "8.0").strip() or "8.0")),
)


async def _get_session(url: str):
    """Get or create an aiohttp session keyed by domain."""
    domain = urlparse(url).netloc or "default"
    if domain in _sessions:
        return _sessions[domain]
    async with _session_lock:
        if domain in _sessions:
            return _sessions[domain]
        try:
            import aiohttp
        except ImportError:
            return None
        timeout = aiohttp.ClientTimeout(
            total=max(
                1.0,
                min(
                    300.0,
                    float(
                        os.getenv("UAR_HTTP_TIMEOUT", "30.0").strip()
                        or "30.0"
                    ),
                ),
            )
        )
        conn = aiohttp.TCPConnector(
            limit=max(
                1,
                min(
                    100,
                    int(
                        os.getenv("UAR_HTTP_POOL_LIMIT", "10").strip()
                        or "10"
                    ),
                ),
            ),
            limit_per_host=max(
                1,
                min(
                    50,
                    int(
                        os.getenv("UAR_HTTP_POOL_PER_HOST", "5").strip()
                        or "5"
                    ),
                ),
            ),
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            force_close=False,
        )
        sess = aiohttp.ClientSession(connector=conn, timeout=timeout)
        _sessions[domain] = sess
        return sess


async def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Any:
    """GET with per-domain pool, circuit breaker, and retry."""
    session = await _get_session(url)
    if session is None:
        raise RuntimeError("aiohttp is required for async HTTP")
    last_exc: BaseException = RuntimeError("No attempts made")
    for attempt in range(_MAX_RETRIES):
        try:
            async with session.get(url, headers=headers, **kwargs) as resp:
                return await resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            delay = min(
                _BASE_DELAY * (2 ** attempt) + random.random(),
                _MAX_DELAY,
            )
            logger.warning(
                f"HTTP GET {url} attempt {attempt + 1} failed: {exc}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)
    raise last_exc


async def http_post(
    url: str,
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Any:
    """POST with per-domain pool and retry."""
    session = await _get_session(url)
    if session is None:
        raise RuntimeError("aiohttp is required for async HTTP")
    last_exc: BaseException = RuntimeError("No attempts made")
    for attempt in range(_MAX_RETRIES):
        try:
            async with session.post(
                url, json=json_data, headers=headers, **kwargs
            ) as resp:
                return await resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            delay = min(
                _BASE_DELAY * (2 ** attempt) + random.random(),
                _MAX_DELAY,
            )
            logger.warning(
                f"HTTP POST {url} attempt {attempt + 1} failed: {exc}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)
    raise last_exc


def close_all_sessions() -> None:
    """Close all cached sessions (call on shutdown)."""
    for domain, sess in list(_sessions.items()):
        try:
            run_sync_safe(sess.close())
        except Exception:
            pass
        del _sessions[domain]
