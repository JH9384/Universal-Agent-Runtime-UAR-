"""API middleware for rate limiting, authentication, and logging"""

import os
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from typing import Dict, Optional, List

import json
import logging
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uar.api.metrics import get_metrics_collector

logger = logging.getLogger(__name__)

# Constants
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_CLEANUP_THRESHOLD = 1024  # number of entries
DEFAULT_CLEANUP_INTERVAL = 100  # number of requests between cleanups
DEFAULT_MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_MAX_ENTRIES = (
    10000  # maximum total entries to prevent unbounded growth
)


def _load_rate_limits() -> Dict[str, Dict[str, int]]:
    """Load rate limits from environment variables with safe defaults"""
    return {
        "default": {
            "requests": int(os.getenv("RATE_LIMIT_ANONYMOUS", "10")),
            "window": int(
                os.getenv("RATE_LIMIT_WINDOW", str(DEFAULT_RATE_LIMIT_WINDOW))
            ),
        },
        "authenticated": {
            "requests": int(os.getenv("RATE_LIMIT_AUTHENTICATED", "100")),
            "window": int(
                os.getenv("RATE_LIMIT_WINDOW", str(DEFAULT_RATE_LIMIT_WINDOW))
            ),
        },
    }


# Rate limiting configuration (loaded from environment)
RATE_LIMITS = _load_rate_limits()


# Thread-safe in-memory rate limiter (for production, use Redis)
class RateLimiter:
    def __init__(
        self,
        cleanup_threshold: int = DEFAULT_CLEANUP_THRESHOLD,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self._request_count = 0
        self._cleanup_threshold = cleanup_threshold
        self._cleanup_interval = cleanup_interval
        self._max_entries = max_entries
        # Track keys in order of first request for O(1) oldest key access
        self._key_order: deque[str] = deque()
        # Use a set for O(1) membership checks alongside deque ordering
        self._key_set: set[str] = set()

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()

        with self._lock:
            request_times = self.requests[key]

            # Track new keys in order (only if not already tracked)
            # Use set for O(1) membership check instead of deque's O(n)
            if key not in self._key_set:
                self._key_order.append(key)
                self._key_set.add(key)
            else:
                # Key already tracked - move to end to track recent use
                # This is safe because we hold the lock
                # Ensure consistency: only move if it's actually in the deque
                if key in self._key_order:
                    self._key_order.remove(key)
                    self._key_order.append(key)
                else:
                    # Inconsistent state: in set but not in deque
                    # Remove from set and re-add to both to ensure consistency
                    self._key_set.discard(key)
                    self._key_order.append(key)
                    self._key_set.add(key)

            # Remove old requests outside the window
            while request_times and request_times[0] <= now - window:
                request_times.popleft()

            if len(request_times) >= limit:
                return False

            request_times.append(now)
            self._request_count += 1

            # Periodic cleanup: only check every N requests to avoid overhead
            # and use double-check pattern to avoid race conditions
            if (
                self._request_count % self._cleanup_interval == 0
                and len(self.requests) > self._cleanup_threshold
            ):
                self._evict_empty_unlocked()

            # Enforce maximum entry cap to prevent unbounded growth
            # If we exceed max_entries, evict oldest entries by key count
            if len(self.requests) > self._max_entries:
                self._enforce_max_entries_unlocked()

            return True

    def _evict_empty_unlocked(self) -> int:
        """Drop empty keys - must be called while holding lock."""
        removed = 0
        # Double-check: verify still empty at deletion time
        for k in list(self.requests.keys()):
            if not self.requests.get(k):  # Double-check with .get() for safety
                self.requests.pop(
                    k, None
                )  # Use pop with default to avoid KeyError
                # Remove from key_order tracking if present
                try:
                    self._key_order.remove(k)
                except ValueError:
                    pass  # Key not in order deque, ignore
                # Remove from key_set as well
                self._key_set.discard(k)
                removed += 1
        return removed

    def _enforce_max_entries_unlocked(self) -> None:
        """Enforce maximum entry cap to prevent unbounded memory growth.

        Must be called while holding lock. Evicts oldest entries by
        removing keys in order of first request (O(1) with deque).
        """
        # Remove oldest entries until we're under the cap
        # Using _key_order deque gives O(1) access to oldest keys
        to_remove = len(self.requests) - self._max_entries
        removed_count = 0
        while removed_count < to_remove and self._key_order:
            oldest_key = self._key_order.popleft()
            if oldest_key in self.requests:
                self.requests.pop(oldest_key, None)
                self._key_set.discard(oldest_key)
                removed_count += 1

    def evict_empty(self) -> int:
        """Drop keys whose window is empty to bound memory over time."""
        with self._lock:
            return self._evict_empty_unlocked()


rate_limiter = RateLimiter()


def reset_rate_limiter():
    """Reset rate limiter state (for testing only)."""
    with rate_limiter._lock:
        rate_limiter.requests.clear()
        rate_limiter._key_order.clear()
        rate_limiter._key_set.clear()
        rate_limiter._request_count = 0


def _load_api_keys() -> Dict[str, Dict]:
    """Load API keys from environment variable.

    Format: comma-separated key:user:tier pairs
    Example: dev-key-12345:developer:authenticated,
             prod-key-67890:production:authenticated
    """
    api_keys_str = os.getenv("API_KEYS", "")
    api_keys = {}

    if api_keys_str:
        for key_entry in api_keys_str.split(","):
            parts = key_entry.strip().split(":")
            if len(parts) >= 2:
                key = parts[0].strip()
                user = parts[1].strip()
                tier = parts[2].strip() if len(parts) > 2 else "authenticated"

                # Validate key and user are not empty
                if not key or not user:
                    logger.warning(
                        f"Skipping invalid API key entry: {key_entry}"
                    )
                    continue

                api_keys[key] = {"user": user, "tier": tier}

    return api_keys


# Load API keys from environment (no hardcoded keys)
API_KEYS = _load_api_keys()

security = HTTPBearer(auto_error=False)


def get_rate_limit_key(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials]
) -> str:
    """Generate rate limit key based on IP and authentication"""
    client_ip = request.client.host if request.client else "unknown"

    if credentials and credentials.credentials in API_KEYS:
        user_info = API_KEYS[credentials.credentials]
        return f"auth:{user_info['user']}:{client_ip}"

    return f"anon:{client_ip}"


def get_rate_limit_for_tier(tier: str) -> tuple[int, int]:
    """Get rate limit for user tier"""
    config = RATE_LIMITS.get(tier, RATE_LIMITS["default"])
    return config["requests"], config["window"]


def rate_limit_middleware(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials]
):
    """Rate limiting middleware"""
    rate_limit_key = get_rate_limit_key(request, credentials)

    tier = "authenticated"
    if not credentials or credentials.credentials not in API_KEYS:
        tier = "default"

    limit, window = get_rate_limit_for_tier(tier)

    # Store rate limit info in request state for later use in response headers
    request.state.rate_limit_tier = tier
    request.state.rate_limit_key = rate_limit_key
    request.state.rate_limit = limit
    request.state.rate_limit_window = window

    if not rate_limiter.is_allowed(rate_limit_key, limit, window):
        logger.warning(f"Rate limit exceeded for {rate_limit_key}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": f"{limit} requests per {window} seconds allowed.",
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
        )


def auth_middleware(credentials: Optional[HTTPAuthorizationCredentials]):
    """Authentication middleware"""
    if not credentials:
        # Allow anonymous access with lower rate limits
        return None

    if credentials.credentials not in API_KEYS:
        logger.warning(
            f"Invalid API key attempted: {credentials.credentials[:8]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Invalid API key",
                "message": "The provided API key is not valid",
            },
        )

    user_info = API_KEYS[credentials.credentials]
    logger.info(f"Authenticated user: {user_info['user']}")
    return user_info


def request_logging_middleware(request: Request, user_info: Optional[Dict]):
    """Request logging middleware"""
    # Use incoming X-Request-ID or generate new correlation id
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    # Add both IDs to request state for tracing
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id

    user_str = f"user:{user_info['user']}" if user_info else "anonymous"
    logger.info(
        f"[cid={correlation_id}][req={request_id}] {request.method} "
        f"{request.url.path} "
        f"from {request.client.host if request.client else 'unknown'} "
        f"({user_str})"
    )

    return request_id


def error_handler_middleware(func):
    """Error handling middleware with consistent error formatting"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise  # Re-raise HTTP exceptions (already properly formatted)
        except Exception as e:
            logger.error(
                f"Unhandled error in {func.__name__}: {str(e)}", exc_info=True
            )
            # Try to get request from args/kwargs for request_id
            request_id = "unknown"
            for arg in args:
                if isinstance(arg, Request):
                    request_id = getattr(arg.state, "request_id", "unknown")
                    break
            if request_id == "unknown" and "request" in kwargs:
                request_id = getattr(
                    kwargs["request"].state, "request_id", "unknown"
                )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                },
            ) from e

    return wrapper


def _get_cors_origins() -> List[str]:
    """Get CORS origins from environment or use safe defaults"""
    cors_origins = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    )
    return [
        origin.strip() for origin in cors_origins.split(",") if origin.strip()
    ]


def apply_middleware(app):
    """Apply all middleware to FastAPI app"""
    from fastapi.middleware.cors import CORSMiddleware

    # CORS middleware - uses environment variable with safe defaults
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request body size limiter
    max_body_size = int(
        os.getenv(
            "MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES)
        )
    )  # 10MB default

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        # Check content length header for early rejection
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            logger.warning(
                f"Request body too large: {content_length} bytes > "
                f"{max_body_size}"
            )
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "Request body too large",
                    "message": f"Maximum body size is {max_body_size} bytes",
                    "code": "BODY_TOO_LARGE",
                },
            )
        return await call_next(request)

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()

        # Get IDs from request state
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        response = await call_next(request)
        process_time = time.time() - start_time

        # Record metrics
        metrics = get_metrics_collector()
        endpoint = f"{request.method} {request.url.path}"
        is_error = response.status_code >= 400
        metrics.record_request(endpoint, process_time, error=is_error)

        # Structured audit log for security/compliance
        audit_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": (
                "AUDIT" if request.url.path.startswith("/api/") else "INFO"
            ),
            "correlation_id": correlation_id,
            "request_id": request_id,
            "client_ip": request.client.host if request.client else None,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(process_time * 1000, 2),
            "user_agent": request.headers.get("user-agent", "unknown"),
            "referer": request.headers.get("referer"),
        }
        logger.info(json.dumps(audit_entry))

        logger.info(
            f"[cid={correlation_id}][req={request_id}] {request.method} "
            f"{request.url.path} "
            f"completed in {process_time:.3f}s with status "
            f"{response.status_code}"
        )

        # Echo correlation ID back to caller
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        # Add rate limit headers using stored state from
        # rate_limit_middleware to avoid race condition
        if (
            hasattr(request.state, "rate_limit_key")
            and hasattr(request.state, "rate_limit")
            and hasattr(request.state, "rate_limit_window")
        ):
            with rate_limiter._lock:
                requests_made = len(
                    rate_limiter.requests.get(
                        request.state.rate_limit_key, deque()
                    )
                )
                limit = request.state.rate_limit
                window = request.state.rate_limit_window
                remaining = max(0, limit - requests_made)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Window"] = str(window)

        return response
