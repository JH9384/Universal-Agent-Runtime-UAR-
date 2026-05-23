"""Rate limiting for remote UOR API calls.

Provides rate limiting to prevent abuse and ensure fair usage
when making remote UOR API calls.
"""

import logging
import time
import threading
from typing import Any, Dict, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Information about rate limit status."""

    allowed: bool
    remaining: int
    reset_time: Optional[float] = None
    retry_after: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "allowed": self.allowed,
            "remaining": self.remaining,
            "reset_time": self.reset_time,
            "retry_after": self.retry_after,
        }


class RateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: float = 60.0,
    ):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, identifier: str) -> RateLimitInfo:
        """Check if request is allowed for identifier.

        Args:
            identifier: Unique identifier (e.g., API key, IP)

        Returns:
            RateLimitInfo with status
        """
        with self.lock:
            now = time.time()
            request_times = self.requests[identifier]

            # Remove requests outside the time window
            cutoff = now - self.window_seconds
            self.requests[identifier] = [
                t for t in request_times if t > cutoff
            ]

            # Check if under limit
            if len(self.requests[identifier]) < self.max_requests:
                self.requests[identifier].append(now)
                return RateLimitInfo(
                    allowed=True,
                    remaining=self.max_requests
                    - len(self.requests[identifier]),
                    reset_time=now + self.window_seconds,
                )
            else:
                # Find when the oldest request expires
                request_list = self.requests[identifier]
                if request_list:
                    oldest = min(request_list)
                    retry_after = oldest + self.window_seconds - now
                    reset_time = oldest + self.window_seconds
                else:
                    retry_after = 0.0
                    reset_time = now + self.window_seconds

                return RateLimitInfo(
                    allowed=False,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=retry_after,
                )

    def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier.

        Args:
            identifier: Unique identifier
        """
        with self.lock:
            if identifier in self.requests:
                del self.requests[identifier]
                logger.info(f"Rate limit reset for: {identifier}")

    def get_stats(self, identifier: str) -> Dict[str, Any]:
        """Get rate limit statistics for identifier.

        Args:
            identifier: Unique identifier

        Returns:
            Dictionary with statistics
        """
        with self.lock:
            request_times = self.requests.get(identifier, [])
            now = time.time()

            # Count requests in current window
            cutoff = now - self.window_seconds
            recent_requests = [t for t in request_times if t > cutoff]

            return {
                "current_requests": len(recent_requests),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "remaining": max(0, self.max_requests - len(recent_requests)),
            }


class SlidingWindowRateLimiter:
    """Rate limiter using sliding window algorithm."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: float = 60.0,
    ):
        """Initialize sliding window rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, identifier: str) -> RateLimitInfo:
        """Check if request is allowed using sliding window.

        Args:
            identifier: Unique identifier

        Returns:
            RateLimitInfo with status
        """
        with self.lock:
            now = time.time()
            request_times = self.requests[identifier]

            # Remove requests outside the window
            cutoff = now - self.window_seconds
            self.requests[identifier] = [
                t for t in request_times if t > cutoff
            ]

            # Check if under limit
            if len(self.requests[identifier]) < self.max_requests:
                self.requests[identifier].append(now)
                return RateLimitInfo(
                    allowed=True,
                    remaining=self.max_requests
                    - len(self.requests[identifier]),
                    reset_time=now + self.window_seconds,
                )
            else:
                # Calculate retry after
                request_list = self.requests[identifier]
                if request_list:
                    oldest = min(request_list)
                    retry_after = oldest + self.window_seconds - now
                    reset_time = oldest + self.window_seconds
                else:
                    retry_after = 0.0
                    reset_time = now + self.window_seconds

                return RateLimitInfo(
                    allowed=False,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=retry_after,
                )


class UORAPIClient:
    """UOR API client with built-in rate limiting."""

    def __init__(
        self,
        base_url: str,
        rate_limiter: Optional[RateLimiter] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize UOR API client.

        Args:
            base_url: Base URL for UOR API
            rate_limiter: Rate limiter instance
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.rate_limiter = rate_limiter or RateLimiter()
        self.api_key = api_key

    def check_rate_limit(self, identifier: str) -> RateLimitInfo:
        """Check if request is allowed.

        Args:
            identifier: Unique identifier (uses API key if set)

        Returns:
            RateLimitInfo with status
        """
        ident = identifier or self.api_key or "default"
        return self.rate_limiter.is_allowed(ident)

    def get_object(self, digest: str) -> Optional[Dict[str, Any]]:
        """Get object by digest with rate limiting.

        Args:
            digest: Object digest

        Returns:
            Object data if successful, None otherwise
        """
        # Check rate limit
        rate_info = self.check_rate_limit(self.api_key or "default")
        if not rate_info.allowed:
            logger.warning(
                f"Rate limit exceeded. Retry after: {rate_info.retry_after}"
            )
            return None

        # Simulate API call (in real implementation, use requests/httpx)
        logger.info(f"Fetching object: {digest}")
        # TODO: Implement actual HTTP request
        return None

    def put_object(self, obj: Dict[str, Any]) -> Optional[str]:
        """Store object with rate limiting.

        Args:
            obj: Object to store

        Returns:
            Digest if successful, None otherwise
        """
        # Check rate limit
        rate_info = self.check_rate_limit(self.api_key or "default")
        if not rate_info.allowed:
            logger.warning(
                f"Rate limit exceeded. Retry after: {rate_info.retry_after}"
            )
            return None

        # Simulate API call
        logger.info("Storing object")
        # TODO: Implement actual HTTP request
        return None
