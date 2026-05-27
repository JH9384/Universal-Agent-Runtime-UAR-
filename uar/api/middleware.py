"""API middleware for rate limiting, authentication, and logging"""

import os
import threading
import time
import uuid
from collections import defaultdict, deque, OrderedDict
from functools import wraps
from typing import Dict, Optional, List, Any

import logging
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uar.api.metrics import get_metrics_collector
from uar.core.audit import get_audit_logger

logger = logging.getLogger(__name__)

# Constants
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_CLEANUP_THRESHOLD = 1024  # number of entries
DEFAULT_CLEANUP_INTERVAL = int(
    os.getenv("RATE_LIMIT_CLEANUP_INTERVAL", "100")
)  # number of requests between cleanups
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


def _load_skill_rate_limits() -> Dict[str, Dict[str, int]]:
    """Load skill-specific rate limits from environment variables.

    Skills can have different rate limits based on their cost:
    - Expensive skills (LLM calls): stricter limits
    - Local skills: relaxed limits
    - I/O intensive skills: moderate limits

    Format: SKILL_RATE_LIMITS=skill1:requests:window,skill2:requests:window
    Example: SKILL_RATE_LIMITS=ollama_generate:5:60,doc_ingest:20:60
    """
    skill_limits = {}
    skill_limits_str = os.getenv("SKILL_RATE_LIMITS", "")

    # Default skill rate limits
    default_skill_limits = {
        # LLM/Generation skills (expensive)
        "ollama_generate": {"requests": 5, "window": 60},
        "openai_chat": {"requests": 5, "window": 60},
        "anthropic_chat": {"requests": 5, "window": 60},
        "gemini_chat": {"requests": 5, "window": 60},
        # GraphRAG (computationally expensive)
        "graphrag_index": {"requests": 2, "window": 300},
        "graphrag_query": {"requests": 10, "window": 60},
        # Document processing (I/O intensive)
        "doc_ingest": {"requests": 20, "window": 60},
        # Local skills (relaxed)
        "dependency_map": {"requests": 50, "window": 60},
        "sum_review": {"requests": 50, "window": 60},
    }

    if skill_limits_str:
        for skill_entry in skill_limits_str.split(","):
            parts = skill_entry.strip().split(":")
            if len(parts) == 3:
                skill = parts[0].strip()
                try:
                    requests = int(parts[1].strip())
                    window = int(parts[2].strip())
                    skill_limits[skill] = {
                        "requests": requests,
                        "window": window,
                    }
                except ValueError:
                    logger.warning(
                        f"Skipping invalid skill rate limit entry "
                        f"(non-numeric values): {skill_entry}"
                    )
            else:
                logger.warning(
                    f"Skipping invalid skill rate limit entry: {skill_entry}"
                )

    # Merge with defaults (env vars override defaults)
    for skill, limits in default_skill_limits.items():
        if skill not in skill_limits:
            skill_limits[skill] = limits

    return skill_limits


# Rate limiting configuration (loaded from environment)
RATE_LIMITS = _load_rate_limits()
SKILL_RATE_LIMITS = _load_skill_rate_limits()


# Thread-safe in-memory rate limiter (for production, use Redis)
# NOTE: All OrderedDict operations are protected by self._lock to ensure
# thread-safety across all Python implementations. Do not rely on GIL for
# atomicity - explicit locking is required.
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
        # Use OrderedDict for O(1) access and ordered iteration
        # This eliminates the race condition between deque and set
        # All operations on _key_order are protected by self._lock
        self._key_order: OrderedDict[str, float] = OrderedDict()

    def is_allowed(
        self, key: str, limit: int, window: int
    ) -> tuple[bool, int]:
        now = time.time()

        with self._lock:
            request_times = self.requests[key]

            # Track keys with timestamp for LRU eviction
            # OrderedDict provides O(1) access and maintains insertion order
            if key not in self._key_order:
                self._key_order[key] = now
            else:
                # Move to end to mark as recently used
                self._key_order.move_to_end(key)

            # Remove old requests outside the window
            while request_times and request_times[0] <= now - window:
                request_times.popleft()

            if len(request_times) >= limit:
                # Return remaining count (which is 0 since limit exceeded)
                return False, 0

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

            # Calculate remaining count while still holding the lock
            remaining = max(0, limit - len(request_times))
            return True, remaining

    def _evict_empty_unlocked(self) -> int:
        """Drop empty keys - must be called while holding lock."""
        removed = 0
        # Double-check: verify still empty at deletion time
        for k in list(self.requests.keys()):
            if not self.requests.get(k):  # Double-check with .get() for safety
                self.requests.pop(
                    k, None
                )  # Use pop with default to avoid KeyError
                # Remove from OrderedDict tracking if present
                self._key_order.pop(k, None)
                removed += 1
        return removed

    def _enforce_max_entries_unlocked(self) -> None:
        """Enforce maximum entry cap to prevent unbounded memory growth.

        Must be called while holding lock. Evicts oldest entries by
        removing keys in order of first request (O(1) with OrderedDict).
        """
        # Keep removing until we're under the cap, even if _key_order
        # contains stale keys not present in self.requests.
        while len(self.requests) > self._max_entries and self._key_order:
            oldest_key, _ = self._key_order.popitem(last=False)
            self.requests.pop(oldest_key, None)

    def evict_empty(self) -> int:
        """Drop keys whose window is empty to bound memory over time."""
        with self._lock:
            return self._evict_empty_unlocked()

    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests without incrementing the counter.

        Args:
            key: Rate limit key
            limit: Request limit
            window: Time window in seconds

        Returns:
            Number of remaining requests allowed
        """
        now = time.time()
        with self._lock:
            request_times = self.requests.get(key)
            if not request_times:
                return limit
            # Remove old requests outside the window
            while request_times and request_times[0] <= now - window:
                request_times.popleft()
            # Update LRU order so inspection doesn't cause eviction
            if key in self._key_order:
                self._key_order.move_to_end(key)
            return max(0, limit - len(request_times))


def reset_rate_limiter():
    """Reset rate limiter state (for testing only)."""
    # rate_limiter is created lazily by create_rate_limiter()
    _rl = globals().get("rate_limiter")
    if _rl is None:
        return
    with _rl._lock:
        _rl.requests.clear()
        _rl._key_order.clear()
        _rl._request_count = 0


class RedisRateLimiter:
    """Redis-backed distributed rate limiter for multi-instance deployments.

    Uses Redis sorted sets with automatic TTL expiration.  Requires
    ``redis`` package and ``REDIS_URL`` environment variable.
    """

    def __init__(self, redis_url: str):
        import redis

        self._redis = redis.from_url(redis_url, decode_responses=True)

    # Lua script: atomic sliding-window check-and-increment.
    # Returns [current_count_after_add, was_allowed] where was_allowed
    # is 1 if the request is within the limit, 0 otherwise.
    # The entry is only added when the request is allowed.
    _LUA_RATE_LIMIT = """
        local key      = KEYS[1]
        local now      = tonumber(ARGV[1])
        local window   = tonumber(ARGV[2])
        local limit    = tonumber(ARGV[3])
        local win_start = now - window
        redis.call('zremrangebyscore', key, 0, win_start)
        local count = redis.call('zcard', key)
        if count >= limit then
            return {count, 0}
        end
        redis.call('zadd', key, now, tostring(now))
        redis.call('expire', key, window)
        return {count + 1, 1}
    """

    def is_allowed(
        self, key: str, limit: int, window: int
    ) -> tuple[bool, int]:
        import redis

        now = time.time()
        zset_key = f"uar:ratelimit:{key}"
        try:
            result: list = self._redis.eval(  # type: ignore[assignment]
                self._LUA_RATE_LIMIT, 1, zset_key,
                now, window, limit,
            )
            count_after, allowed_flag = int(result[0]), int(result[1])
        except redis.RedisError:
            # Redis unavailable: permissive fallback
            return True, limit - 1
        if not allowed_flag:
            return False, 0
        remaining = max(0, limit - count_after)
        return True, remaining

    def get_remaining(self, key: str, limit: int, window: int) -> int:
        import redis

        window_start = time.time() - window
        try:
            self._redis.zremrangebyscore(
                f"uar:ratelimit:{key}", 0, window_start
            )
            current = int(self._redis.zcard(f"uar:ratelimit:{key}"))  # type: ignore[arg-type]
        except redis.RedisError:
            return limit
        return max(0, limit - current)


def create_rate_limiter() -> RateLimiter:
    """Factory: return RedisRateLimiter if REDIS_URL is set, else in-memory.

    In production (ENVIRONMENT=production), Redis is **required**.
    Startup will fail with a clear error if REDIS_URL is missing or
    the Redis server is unreachable.
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production"

    if redis_url:
        try:
            return RedisRateLimiter(redis_url)  # type: ignore[return-value]
        except ImportError:
            msg = (
                "REDIS_URL is set but the redis package is not installed. "
                "Install it with: pip install redis"
            )
            if is_production:
                raise RuntimeError(msg) from None
            logger.warning(msg + "; falling back to in-memory rate limiter")
        except Exception as exc:  # noqa: BLE001
            msg = f"Failed to connect to Redis at {redis_url}: {exc}"
            if is_production:
                raise RuntimeError(msg) from exc
            logger.error(msg + "; falling back to in-memory rate limiter")

    if is_production:
        raise RuntimeError(
            "ENVIRONMENT=production requires REDIS_URL to be set "
            "for shared rate limiting across workers. "
            "Add Redis to your deployment and set REDIS_URL, e.g. "
            "REDIS_URL=redis://localhost:6379/0"
        )

    return RateLimiter()


# Replace the module-level instance with the factory result so that
# importing modules always get the correct backend.
rate_limiter = create_rate_limiter()


def _load_api_keys() -> Dict[str, Dict]:
    """Load API keys from environment variable or file.

    Format: comma-separated key:user:tier pairs
    If API_KEYS_FILE is set, reads keys from that file instead.
    """
    api_keys: Dict[str, Dict] = {}
    api_keys_file = os.getenv("API_KEYS_FILE", "").strip()
    if api_keys_file:
        try:
            with open(api_keys_file, "r", encoding="utf-8") as f:
                api_keys_str = f.read().strip()
        except OSError as exc:
            logger.error(
                "Cannot read API_KEYS_FILE %s: %s", api_keys_file, exc
            )
            return api_keys
    else:
        api_keys_str = os.getenv("API_KEYS", "")

    if api_keys_str:
        for key_entry in api_keys_str.split(","):
            parts = key_entry.strip().split(":")
            if len(parts) >= 2:
                key = parts[0].strip()
                user = parts[1].strip()
                tier = parts[2].strip() if len(parts) > 2 else "authenticated"
                if not key or not user:
                    logger.warning(
                        f"Skipping invalid API key entry: {key_entry}"
                    )
                    continue
                api_keys[key] = {"user": user, "tier": tier}

    return api_keys


# Load API keys from environment (no hardcoded keys)
API_KEYS = _load_api_keys()
_API_KEYS_FILE = os.getenv("API_KEYS_FILE", "").strip()
_API_KEYS_MTIME = 0.0
if _API_KEYS_FILE:
    try:
        _API_KEYS_MTIME = os.path.getmtime(_API_KEYS_FILE)
    except OSError:
        pass

# Thread-safe lock for hot-reloading API keys
_api_keys_lock = threading.Lock()


def _maybe_reload_api_keys() -> None:
    """Hot-reload API keys if API_KEYS_FILE has changed.

    Thread-safe: concurrent requests will block on the lock
    during reload, ensuring they always see a consistent key set.
    """
    global API_KEYS, _API_KEYS_MTIME
    if not _API_KEYS_FILE:
        return
    with _api_keys_lock:
        try:
            mtime = os.path.getmtime(_API_KEYS_FILE)
        except OSError:
            return
        if mtime > _API_KEYS_MTIME:
            _API_KEYS_MTIME = mtime
            new_keys = _load_api_keys()
            if new_keys:
                API_KEYS = new_keys
                logger.info("API keys reloaded from %s", _API_KEYS_FILE)


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


def _extract_skill_from_request_data(
    skills: Optional[List[str]],
    execution_order: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    """Extract skill name from request data for WebSocket endpoints.

    Args:
        skills: List of skill names
        execution_order: Execution order with skills and recipes

    Returns:
        First skill name or None
    """
    from uar.core.recipes import get_recipe_skills

    skill_name = None
    if skills and len(skills) > 0:
        skill_name = skills[0]
    elif execution_order and len(execution_order) > 0:
        first_item = execution_order[0]
        if first_item.get("type") == "skill":
            content = first_item.get("content")
            if content is not None and isinstance(content, str):
                skill_name = content
        elif first_item.get("type") == "recipe":
            content = first_item.get("content")
            if content is not None and isinstance(content, str):
                recipe_skills = get_recipe_skills(content)
                if recipe_skills and len(recipe_skills) > 0:
                    skill_name = recipe_skills[0]

    return skill_name


def check_rate_limit(
    rate_limit_key: str, tier: str, skill_name: Optional[str]
) -> tuple[int, int, str]:
    """Check rate limit and return limit, window, and rate limit type.

    Args:
        rate_limit_key: Unique key for rate limiting
        tier: User tier (authenticated or default)
        skill_name: First skill name for skill-specific limits

    Returns:
        Tuple of (limit, window, rate_limit_type)
    """
    # Check for skill-specific rate limits
    if skill_name and skill_name in SKILL_RATE_LIMITS:
        limit = SKILL_RATE_LIMITS[skill_name]["requests"]
        window = SKILL_RATE_LIMITS[skill_name]["window"]
        rate_limit_type = "skill"
    else:
        limit, window = get_rate_limit_for_tier(tier)
        rate_limit_type = "tier"

    return limit, window, rate_limit_type


def build_rate_limit_key(
    client_ip: str, credentials: Optional[HTTPAuthorizationCredentials]
) -> tuple[str, str]:
    """Build rate limit key and determine tier from credentials.

    Shared function for both HTTP and WebSocket endpoints to ensure
    consistent rate limiting logic.

    Args:
        client_ip: Client IP address
        credentials: Optional HTTP authorization credentials

    Returns:
        Tuple of (rate_limit_key, tier)
    """
    if credentials and credentials.credentials in API_KEYS:
        user_info = API_KEYS[credentials.credentials]
        tier = user_info.get("tier", "authenticated")
        rate_limit_key = f"auth:{user_info['user']}:{client_ip}"
    else:
        tier = "default"
        rate_limit_key = f"anon:{client_ip}"

    return rate_limit_key, tier


def rate_limit_middleware(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
    first_skill: Optional[str] = None,
):
    """Rate limiting middleware with skill-specific limits.

    Args:
        request: FastAPI Request object.
        credentials: Optional bearer token credentials.
        first_skill: Optional pre-parsed first skill name. When provided,
            this is used instead of trying to extract from the request body,
            avoiding ASGI stream consumption.
    """
    # Use shared function to get rate limit key and tier in one call
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)

    # Check for skill-specific rate limits
    # Body extraction was removed; callers supply first_skill directly.
    skill_name = first_skill
    if skill_name and skill_name in SKILL_RATE_LIMITS:
        limit = SKILL_RATE_LIMITS[skill_name]["requests"]
        window = SKILL_RATE_LIMITS[skill_name]["window"]
        rate_limit_type = "skill"
    else:
        limit, window = get_rate_limit_for_tier(tier)
        rate_limit_type = "tier"

    # Store rate limit info in request state for later use in response headers
    request.state.rate_limit_tier = tier
    request.state.rate_limit_key = rate_limit_key
    request.state.rate_limit = limit
    request.state.rate_limit_window = window
    request.state.rate_limit_type = rate_limit_type
    if skill_name:
        request.state.skill_name = skill_name

    allowed, remaining = rate_limiter.is_allowed(rate_limit_key, limit, window)
    if not allowed:
        logger.warning(f"Rate limit exceeded for {rate_limit_key}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": f"{limit} requests per {window} seconds allowed.",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "skill": skill_name if skill_name else None,
                "rate_limit_type": rate_limit_type,
            },
        )

    # Store remaining count from is_allowed (calculated while holding lock)
    request.state.rate_limit_remaining = remaining


def auth_middleware(credentials: Optional[HTTPAuthorizationCredentials]):
    """Authentication middleware"""
    _maybe_reload_api_keys()
    if not credentials:
        # Allow anonymous access with lower rate limits
        return None

    with _api_keys_lock:
        key_valid = credentials.credentials in API_KEYS
        if key_valid:
            user_info = API_KEYS[credentials.credentials].copy()

    if not key_valid:
        logger.warning(
            f"Invalid API key attempted: {credentials.credentials[:8]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Invalid API key",
                "error_code": "INVALID_API_KEY",
                "message": "The provided API key is not valid",
            },
        )

    logger.info(f"Authenticated user: {user_info['user']}")
    return user_info


_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "token",
        "key",
        "secret",
        "password",
        "passwd",
        "api_key",
        "apikey",
        "auth",
        "credential",
        "session",
        "jwt",
        "bearer",
    }
)


def _redact_query_params(url) -> str:
    """Return URL query string with sensitive values masked."""
    if not url.query:
        return ""
    from urllib.parse import parse_qsl, urlencode

    params = parse_qsl(url.query)
    redacted = []
    for k, v in params:
        if k.lower() in _SENSITIVE_QUERY_KEYS:
            redacted.append((k, "***"))
        else:
            redacted.append((k, v))
    # safe='*' keeps the redaction placeholder readable in logs
    return "?" + urlencode(redacted, safe="*")


def request_logging_middleware(request: Request, user_info: Optional[Dict]):
    """Request logging middleware"""
    # Use incoming X-Request-ID or generate new correlation id
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    # Add both IDs to request state for tracing
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id

    # Build safe URL for logging (redact sensitive query params)
    safe_query = _redact_query_params(request.url)
    safe_url = f"{request.url.path}{safe_query}"

    user_str = f"user:{user_info['user']}" if user_info else "anonymous"
    logger.info(
        f"[cid={correlation_id}][req={request_id}] {request.method} "
        f"{safe_url} "
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
                    "error_code": "INTERNAL_SERVER_ERROR",
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
    """Apply all middleware to FastAPI app

    Middleware execution order in FastAPI:
    1. add_middleware() runs BEFORE @app.middleware decorators
    2. Among @app.middleware decorators, LAST registered runs FIRST (LIFO)

    Actual execution order (outermost to innermost):
    1. log_requests (last @app.middleware registered)
    2. api_version_rewrite (second to last @app.middleware)
    3. limit_request_body (first @app.middleware registered)

    Note: CORS is already applied in server.py via add_middleware.
    """
    # Request body size limiter
    # Runs last (innermost) - first @app.middleware registered
    max_body_size = int(
        os.getenv(
            "MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES)
        )
    )  # 10MB default

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        # Check content length header for early rejection
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_body_size:
                    logger.warning(
                        f"Request body too large: {content_length} bytes > "
                        f"{max_body_size}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error": "Request body too large",
                            "error_code": "BODY_TOO_LARGE",
                            "message": (
                                f"Maximum body size is {max_body_size} bytes"
                            ),
                        },
                    )
            except ValueError:
                # Malformed Content-Length header; let downstream handle it
                pass
        return await call_next(request)

    # API version rewrite — supports /api/v1/ as alias for /api/
    # Runs second to last - second @app.middleware registered
    @app.middleware("http")
    async def api_version_rewrite(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/"):
            request.scope["path"] = path.replace("/api/v1/", "/api/", 1)
        return await call_next(request)

    # Request logging middleware
    # Runs second (outermost after CORS) - last @app.middleware registered
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
        if request.url.path.startswith("/api/"):
            audit = get_audit_logger()
            audit.write(
                event_type="api_access",
                actor=getattr(request.state, "user_id", "anonymous"),
                action=request.method,
                resource=request.url.path,
                outcome=(
                    "success" if response.status_code < 400 else "failure"
                ),
                details={
                    "status_code": response.status_code,
                    "duration_ms": round(process_time * 1000, 2),
                },
                request_id=request_id,
                client_ip=(
                    request.client.host if request.client else None
                ),
            )

        logger.info(
            f"[cid={correlation_id}][req={request_id}] {request.method} "
            f"{request.url.path} "
            f"completed in {process_time:.3f}s with status "
            f"{response.status_code}"
        )

        # Echo correlation ID back to caller
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        # Add rate limit headers using stored remaining count from
        # rate_limit_middleware to avoid race conditions
        if (
            hasattr(request.state, "rate_limit_key")
            and hasattr(request.state, "rate_limit")
            and hasattr(request.state, "rate_limit_window")
            and hasattr(request.state, "rate_limit_remaining")
        ):
            limit = request.state.rate_limit
            window = request.state.rate_limit_window
            remaining = request.state.rate_limit_remaining
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(window)

        return response

    # Security headers middleware
    # Runs first (outermost) - last @app.middleware registered
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src *"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        # HSTS only in production
        if os.getenv("ENVIRONMENT", "").lower() == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
