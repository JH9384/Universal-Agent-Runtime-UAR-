"""Retry decorator for skill execution with exponential backoff.

Provides a convenient decorator to wrap functions with retry logic,
exponential backoff, and configurable retry policies.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Type, Tuple, Optional
from .exceptions import SkillExecutionError, TimeoutError

logger = logging.getLogger(__name__)

# Default retry policy
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_BASE = 2
DEFAULT_MAX_BACKOFF = 5


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: int = DEFAULT_BACKOFF_BASE,
    max_backoff: int = DEFAULT_MAX_BACKOFF,
    retry_on: Tuple[Type[Exception], ...] = (
        SkillExecutionError,
        TimeoutError,
    ),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """Decorator to wrap a function with retry logic and exponential backoff.

    Usage:
        @with_retry(max_retries=3, backoff_base=2)
        def my_skill(ctx):
            # Skill execution
            pass

    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        backoff_base: Base for exponential backoff (default: 2)
        max_backoff: Maximum backoff in seconds (default: 5)
        retry_on: Tuple of exception types to retry on
        on_retry: Optional callback function called on each retry
                  Receives (attempt_number, exception) as arguments

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    last_error = exc
                    if attempt < max_retries:
                        backoff = min(backoff_base**attempt, max_backoff)
                        logger.warning(
                            "Retry %s/%s for %s after %ss: %s",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            backoff,
                            exc,
                        )
                        if on_retry:
                            on_retry(attempt + 1, exc)
                        time.sleep(backoff)
                    else:
                        logger.error(
                            "Max retries (%s) exceeded for %s: %s",
                            max_retries,
                            func.__name__,
                            exc,
                        )
                        raise

            # This should never be reached, but for type safety
            raise (
                last_error
                if last_error
                else Exception("Unexpected error in retry")
            )

        return wrapper

    return decorator


def get_retry_policy(skill_name: str) -> int:
    """Get retry policy for a specific skill.

    Args:
        skill_name: Name of the skill

    Returns:
        Maximum number of retries for the skill
    """
    # Import here to avoid circular dependency
    from .executor import SKILL_RETRY_POLICIES

    return SKILL_RETRY_POLICIES.get(skill_name, DEFAULT_MAX_RETRIES)
