"""API middleware for rate limiting, authentication, and logging"""

import os
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from typing import Dict, Optional, List

import logging
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

def _load_rate_limits() -> Dict[str, Dict[str, int]]:
    """Load rate limits from environment variables with safe defaults"""
    return {
        "default": {
            "requests": int(os.getenv("RATE_LIMIT_ANONYMOUS", "10")),
            "window": int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        },
        "authenticated": {
            "requests": int(os.getenv("RATE_LIMIT_AUTHENTICATED", "100")),
            "window": int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        },
    }


# Rate limiting configuration (loaded from environment)
RATE_LIMITS = _load_rate_limits()

# Thread-safe in-memory rate limiter (for production, use Redis)
class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        
        with self._lock:
            request_times = self.requests[key]
            
            # Remove old requests outside the window
            while request_times and request_times[0] <= now - window:
                request_times.popleft()
            
            if len(request_times) >= limit:
                return False
            
            request_times.append(now)
            return True

rate_limiter = RateLimiter()


def _load_api_keys() -> Dict[str, Dict]:
    """Load API keys from environment variable.
    
    Format: comma-separated key:user:tier pairs
    Example: dev-key-12345:developer:authenticated,prod-key-67890:production:authenticated
    """
    api_keys_str = os.getenv("API_KEYS", "")
    api_keys = {}
    
    if api_keys_str:
        for key_entry in api_keys_str.split(","):
            parts = key_entry.strip().split(":")
            if len(parts) >= 2:
                key = parts[0]
                user = parts[1]
                tier = parts[2] if len(parts) > 2 else "authenticated"
                api_keys[key] = {"user": user, "tier": tier}
    
    return api_keys


# Load API keys from environment (no hardcoded keys)
API_KEYS = _load_api_keys()

security = HTTPBearer(auto_error=False)

def get_rate_limit_key(request: Request, credentials: Optional[HTTPAuthorizationCredentials]) -> str:
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

def rate_limit_middleware(request: Request, credentials: Optional[HTTPAuthorizationCredentials]):
    """Rate limiting middleware"""
    rate_limit_key = get_rate_limit_key(request, credentials)
    
    tier = "authenticated"
    if not credentials or credentials.credentials not in API_KEYS:
        tier = "default"
    
    limit, window = get_rate_limit_for_tier(tier)
    
    if not rate_limiter.is_allowed(rate_limit_key, limit, window):
        logger.warning(f"Rate limit exceeded for {rate_limit_key}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. {limit} requests per {window} seconds allowed."
        )

def auth_middleware(credentials: Optional[HTTPAuthorizationCredentials]):
    """Authentication middleware"""
    if not credentials:
        # Allow anonymous access with lower rate limits
        return None
    
    if credentials.credentials not in API_KEYS:
        logger.warning(f"Invalid API key attempted: {credentials.credentials[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    user_info = API_KEYS[credentials.credentials]
    logger.info(f"Authenticated user: {user_info['user']}")
    return user_info

def request_logging_middleware(request: Request, user_info: Optional[Dict]):
    """Request logging middleware"""
    request_id = str(uuid.uuid4())
    
    # Add request ID to request state for tracing
    request.state.request_id = request_id
    
    user_str = f"user:{user_info['user']}" if user_info else "anonymous"
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'} ({user_str})"
    )
    
    return request_id

def error_handler_middleware(func):
    """Error handling middleware with consistent error formatting"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        try:
            return await func(request, *args, **kwargs)
        except HTTPException:
            raise  # Re-raise HTTP exceptions (already properly formatted)
        except Exception as e:
            logger.error(f"Unhandled error in {func.__name__}: {str(e)}", exc_info=True)
            # Get request_id from request state if available
            request_id = getattr(request.state, 'request_id', 'unknown')
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id
                }
            ) from e
    return wrapper

def _get_cors_origins() -> List[str]:
    """Get CORS origins from environment or use safe defaults"""
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in cors_origins.split(",") if origin.strip()]


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
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Get request ID from request state (set by auth middleware)
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"completed in {process_time:.3f}s with status {response.status_code}"
        )
        
        return response
