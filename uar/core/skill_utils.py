"""Shared utilities for UAR skill authors.

Provides decorators that eliminate boilerplate error handling
across skill implementations.
"""

from __future__ import annotations

import importlib.util
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def skill_guard(
    operation_name: str,
    *,
    status: str = "error",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that wraps a skill in canonical error handling.

    Catches any uncaught exception, logs it at ERROR level, and returns
    the standard UAR error dict so the pipeline can continue gracefully.

    Args:
        operation_name: Human-readable name used in log messages.
        status: Value for the ``"status"`` key in the error response.
            Use ``"error"`` for framework wrappers (default) or
            ``"failed"`` for computation skills.

    Usage::

        @register_skill("my_skill")
        @skill_guard("My skill", status="failed")
        def my_skill(ctx: PipelineContext) -> Dict[str, Any]:
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        mod_logger = logging.getLogger(fn.__module__)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                mod_logger.exception("%s failed", operation_name)
                return {
                    "status": status,
                    "error": f"{type(exc).__name__}: {exc}",
                    "message": f"{operation_name} failed",
                }

        return wrapper

    return decorator


def require_package(
    package: Union[str, List[str]], *,
    install_hint: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Return an error dict if *package* is not importable, else ``None``.

    Eliminates the duplicated ``importlib.util.find_spec`` guard that
    exists across many optional-dependency skills.

    Args:
        package: Package name or list of package names to check.
        install_hint: Optional hint shown in the error message.

    Usage::

        err = require_package("scipy", install_hint="pip install scipy")
        if err:
            return err

        err = require_package(
            ["matplotlib", "numpy"],
            install_hint="pip install matplotlib numpy",
        )
        if err:
            return err
    """
    packages = [package] if isinstance(package, str) else package
    missing = []
    for p in packages:
        if not p:
            missing.append("<empty>")
            continue
        try:
            if importlib.util.find_spec(p) is None:
                missing.append(p)
        except ValueError:
            # Module present in sys.modules but __spec__ not set
            # (e.g. test mocks) — treat as available.
            pass
    if not missing:
        return None

    hint = install_hint or f"pip install {' '.join(missing)}"
    pkg_list = ", ".join(missing)
    return {
        "status": "failed",
        "error": f"{pkg_list} not installed. {hint}",
    }
