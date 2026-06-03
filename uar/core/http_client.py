"""Shared HTTP client with per-domain connection pools
and exponential backoff retry.
"""

import asyncio
import collections
import logging
import os
import random
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from uar.core.validation_utils import validate_url

logger = logging.getLogger(__name__)

# Per-domain aiohttp session cache (bounded FIFO)
_sessions: "collections.OrderedDict[str, Any]" = collections.OrderedDict()
_session_lock = asyncio.Lock()
_MAX_SESSIONS = max(
    1,
    min(
        256,
        int(
            os.getenv("UAR_HTTP_MAX_SESSIONS", "32").strip()
            or "32"
        ),
    ),
)


def _get_int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        raw = os.getenv(name, str(default)).strip() or str(default)
        return max(lo, min(hi, int(raw)))
    except (ValueError, TypeError):
        return default


def _get_float_env(name: str, default: float, lo: float, hi: float) -> float:
    try:
        raw = os.getenv(name, str(default)).strip() or str(default)
        return max(lo, min(hi, float(raw)))
    except (ValueError, TypeError):
        return default


# Retry configuration
_MAX_RETRIES = _get_int_env("UAR_HTTP_MAX_RETRIES", 3, 0, 10)
_BASE_DELAY = _get_float_env("UAR_HTTP_BASE_DELAY", 0.5, 0.0, 5.0)
_MAX_DELAY = _get_float_env("UAR_HTTP_MAX_DELAY", 8.0, 0.0, 60.0)


async def _get_session(url: str):
    """Get or create an aiohttp session keyed by domain."""
    domain = urlparse(url).netloc or "default"
    try:
        return _sessions[domain]
    except KeyError:
        pass
    async with _session_lock:
        if domain in _sessions:  # pragma: no cover
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
        # Evict oldest sessions if at capacity (close after releasing lock)
        to_close = []
        while len(_sessions) >= _MAX_SESSIONS:
            oldest_domain, oldest_sess = _sessions.popitem(last=False)
            to_close.append((oldest_domain, oldest_sess))
        sess = aiohttp.ClientSession(connector=conn, timeout=timeout)
        _sessions[domain] = sess
    for oldest_domain, oldest_sess in to_close:
        try:
            await oldest_sess.close()
        except Exception:
            logger.exception("Session close failed for %s", oldest_domain)
    return sess


def _is_client_error(exc: BaseException) -> bool:
    """Return True for 4xx client errors that should not be retried."""
    status = getattr(exc, "status", None)
    return isinstance(status, int) and 400 <= status <= 499


async def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Any:
    """GET with per-domain pool and retry."""
    validate_url(url, field_name="url")
    session = await _get_session(url)
    if session is None:
        raise RuntimeError("aiohttp is required for async HTTP")
    last_exc: BaseException = RuntimeError("No attempts made")
    for attempt in range(_MAX_RETRIES):
        try:
            async with session.get(url, headers=headers, **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as exc:
            if _is_client_error(exc):
                raise
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            delay = min(
                _BASE_DELAY * (2 ** attempt) + random.random(),
                _MAX_DELAY,
            )
            logger.warning(
                "HTTP GET %s attempt %s failed: %s. Retrying in %.2fs",
                url,
                attempt + 1,
                exc,
                delay,
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
    validate_url(url, field_name="url")
    session = await _get_session(url)
    if session is None:
        raise RuntimeError("aiohttp is required for async HTTP")
    last_exc: BaseException = RuntimeError("No attempts made")
    for attempt in range(_MAX_RETRIES):
        try:
            async with session.post(
                url, json=json_data, headers=headers, **kwargs
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as exc:
            if _is_client_error(exc):
                raise
            last_exc = exc
            if attempt == _MAX_RETRIES - 1:
                break
            delay = min(
                _BASE_DELAY * (2 ** attempt) + random.random(),
                _MAX_DELAY,
            )
            logger.warning(
                "HTTP POST %s attempt %s failed: %s. Retrying in %.2fs",
                url,
                attempt + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    raise last_exc


async def close_all_sessions() -> None:
    """Close all cached sessions (call on shutdown)."""
    async with _session_lock:
        for domain, sess in list(_sessions.items()):
            try:
                await sess.close()
            except Exception:
                logger.exception("Session close failed for %s", domain)
        _sessions.clear()
