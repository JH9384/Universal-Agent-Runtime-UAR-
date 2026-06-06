"""Shared utilities for UAR skill authors.

Provides decorators that eliminate boilerplate error handling
across skill implementations.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

from .exceptions import UARError

logger = logging.getLogger(__name__)


def wrap_with_digest(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add a UOR content-addressed digest to a result dict.

    Best-effort: silently skip if compute_uor_digest is unavailable,
    raises, or if the result already carries a ``uor_digest`` key
    (e.g. skills that compute their own content address).
    """
    if not isinstance(result, dict):
        return result
    if "uor_digest" in result:
        return result
    try:
        from uar.uor.bounded_json import compute_uor_digest

        result["uor_digest"] = compute_uor_digest(result)
    except Exception:
        pass
    return result


# Backward-compatible alias used by existing callers
_wrap_with_digest = wrap_with_digest


def skill_guard(
    operation_name: str,
    *,
    status: str = "error",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that wraps a skill in canonical error handling.

    Catches unexpected exceptions, logs them at ERROR level, and returns
    the standard UAR error dict so the pipeline can continue gracefully.

    Framework-level exceptions (subclasses of :class:`UARError`) are
    **not** caught — they propagate to the executor so that retry,
    circuit-breaker, and timeout logic work correctly.

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

        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = await fn(*args, **kwargs)
                    return wrap_with_digest(result)
                except UARError:
                    raise
                except Exception as exc:
                    mod_logger.exception("%s failed", operation_name)
                    return wrap_with_digest({
                        "status": status,
                        "error": f"{type(exc).__name__}: {exc}",
                        "message": f"{operation_name} failed",
                    })

            return async_wrapper

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = fn(*args, **kwargs)
                return wrap_with_digest(result)
            except UARError:
                raise
            except Exception as exc:
                mod_logger.exception("%s failed", operation_name)
                return wrap_with_digest({
                    "status": status,
                    "error": f"{type(exc).__name__}: {exc}",
                    "message": f"{operation_name} failed",
                })

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


def require_field(
    meta: Dict[str, Any],
    key: str,
    error_msg: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return error dict if *key* is missing or falsy in *meta*, else ``None``.

    Eliminates the duplicated early-validation guard that exists across
    many ecosystem and utility skills.

    Args:
        meta: The skill's metadata dict (usually ``ctx.goal.metadata``).
        key: Required metadata key.
        error_msg: Optional custom error message.  Defaults to
            ``"metadata '<key>' required"``.

    Usage::

        err = require_field(meta, "digest")
        if err:
            return err
    """
    value = meta.get(key)
    if value:
        return None
    msg = error_msg or f"metadata '{key}' required"
    return {"status": "failed", "error": msg}
