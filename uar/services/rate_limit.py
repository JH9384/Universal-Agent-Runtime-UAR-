"""Rate limiting service — centralised key building and checking.

Eliminates duplicated rate-limit setup code in WebSocket handlers
and HTTP endpoints.
"""

from typing import Any, Optional, Tuple
from fastapi.security import HTTPAuthorizationCredentials
from uar.api.middleware import (
    build_rate_limit_key,
    rate_limiter,
    RATE_LIMITS,
)
from .base import BaseService


class RateLimitService(BaseService):
    """Encapsulates rate-limit checks with uniform error formatting."""

    def check(
        self,
        client_ip: str,
        credentials: Optional[HTTPAuthorizationCredentials],
    ) -> Tuple[bool, str, dict[str, int]]:
        """Check if request is allowed under rate limits.

        Returns:
            Tuple of (allowed, tier_name, limit_dict).
        """
        rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
        limit = RATE_LIMITS.get(tier, RATE_LIMITS["default"])
        allowed, _ = rate_limiter.is_allowed(
            rate_limit_key, limit["requests"], limit["window"]
        )
        return allowed, tier, limit

    async def ws_close_if_denied(self, allowed: bool, websocket: Any) -> bool:
        """Close WebSocket with policy-violation code if denied.

        Returns True if allowed, False if connection was closed.
        """
        if not allowed:
            try:
                await websocket.close(code=1008, reason="Rate limit exceeded")
            except (RuntimeError, ConnectionError, TypeError):
                pass
            return False
        return True
