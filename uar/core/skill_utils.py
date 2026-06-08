"""Shared utilities for UAR skill authors.

Provides decorators that eliminate boilerplate error handling
across skill implementations.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from .exceptions import UARError

logger = logging.getLogger(__name__)


def normalize_skill_result(result: Any) -> Any:
    """Apply small compatibility normalizations to skill result dicts."""
    if not isinstance(result, dict):
        return result
    if "status" in result:
        return result
    errors = result.get("errors")
    document_count = result.get("document_count")
    if errors and document_count == 0:
        normalized = dict(result)
        normalized["status"] = "failed"
        if "error" not in normalized or normalized.get("error") is None:
            normalized["error"] = errors[0] if isinstance(errors, list) else errors
        return normalized
    return result


def wrap_with_digest(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add a UOR content-addressed digest to a result dict.

    Best-effort: silently skip if compute_uor_digest is unavailable,
    raises, or if the result already carries a ``uor_digest`` key
    (e.g. skills that compute their own content address).
    """
    result = normalize_skill_result(result)
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
    """Decorator that wraps a skill in canonical error handling."""

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


def require_field(
    mapping: Mapping[str, Any] | None,
    field: str,
    *,
    label: str = "metadata",
    status: str = "failed",
) -> Optional[Dict[str, str]]:
    """Return an error dict if a required field is missing or empty.

    Several skill modules use this small guard to keep input validation
    consistent without raising during skill registration or execution.
    """
    if mapping is None:
        return {"status": status, "error": f"{field} is required in {label}"}

    value = mapping.get(field)
    if value is None or value == "":
        return {"status": status, "error": f"{field} is required in {label}"}

    return None


def require_env(
    name: Union[str, List[str]], *,
    install_hint: Optional[str] = None,
    status: str = "failed",
) -> Optional[Dict[str, str]]:
    """Return an error dict if required environment variables are missing."""
    names = [name] if isinstance(name, str) else name
    missing = [env_name for env_name in names if not os.getenv(env_name)]
    if not missing:
        return None

    hint = f" {install_hint}" if install_hint else ""
    env_list = ", ".join(missing)
    return {
        "status": status,
        "error": f"Missing required environment variable(s): {env_list}.{hint}".strip(),
    }


def require_path(
    mapping: Mapping[str, Any] | None,
    field: str,
    *,
    error_msg: Optional[str] = None,
    label: str = "metadata",
    status: str = "failed",
) -> Optional[Dict[str, str]]:
    """Return an error dict if a required path field is missing or invalid."""
    missing = require_field(mapping, field, label=label, status=status)
    if missing:
        if error_msg:
            missing["error"] = error_msg
        return missing

    assert mapping is not None
    value = mapping.get(field)
    try:
        path = Path(os.fspath(value))
    except TypeError:
        return {"status": status, "error": error_msg or f"{field} is not a valid path"}

    if not path.exists():
        return {"status": status, "error": error_msg or f"{field} does not exist: {path}"}

    return None


def require_package(
    package: Union[str, List[str]], *,
    install_hint: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Return an error dict if *package* is not importable, else ``None``."""
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
