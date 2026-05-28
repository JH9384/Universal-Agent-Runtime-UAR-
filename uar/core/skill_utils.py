"""Shared utilities for UAR skill authors.

Provides decorators that eliminate boilerplate error handling
across skill implementations.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable


def skill_guard(
    operation_name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that wraps a skill in canonical error handling.

    Catches any uncaught exception, logs it at ERROR level, and returns
    the standard UAR error dict so the pipeline can continue gracefully.

    Usage::

        @register_skill("my_skill")
        @skill_guard("My skill")
        def my_skill(ctx: PipelineContext) -> Dict[str, Any]:
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        logger = logging.getLogger(fn.__module__)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("%s failed", operation_name)
                return {
                    "status": "error",
                    "error": "Internal error",
                    "message": f"{operation_name} failed",
                }

        return wrapper

    return decorator
