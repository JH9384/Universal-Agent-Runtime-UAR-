from __future__ import annotations

import importlib.util
import threading
from typing import Any, Callable, Dict, List
from functools import wraps

from .exceptions import SkillNotFoundError, ValidationError


class SkillRegistry:
    """Thread-safe registry of named pipeline skills.

    Registration is idempotent failure (raises on duplicate names) and
    listing returns a snapshot — no caching, because the previous
    ``@lru_cache`` decorator on a bound method silently returned a
    stale list whenever new skills were registered after the first
    call.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Callable] = {}
        self._lock = threading.RLock()

    def register(self, name: str, fn: Callable) -> None:
        """Register a skill with validation."""
        if not name or not isinstance(name, str):
            raise ValidationError(
                "Skill name must be a non-empty string", field="name"
            )

        if not callable(fn):
            raise ValidationError(
                "Skill function must be callable", field="function"
            )

        with self._lock:
            if name in self._skills:
                raise ValidationError(
                    f"Skill '{name}' is already registered", field="name"
                )
            self._skills[name] = fn

    def get(self, name: str) -> Callable:
        """Look up a registered skill by name."""
        with self._lock:
            fn = self._skills.get(name)
        if fn is None:
            raise SkillNotFoundError(name)
        return fn

    def list(self) -> List[str]:
        """Return a sorted snapshot of registered skill names."""
        with self._lock:
            return sorted(self._skills.keys())

    def is_registered(self, name: str) -> bool:
        """Return whether ``name`` is registered."""
        with self._lock:
            return name in self._skills


registry = SkillRegistry()


def register_skill(name: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        registry.register(name, fn)
        return fn

    return decorator


def requires_package(
    package: str, *, install_hint: str = ""
) -> Callable[[Callable], Callable]:
    """Decorator that checks an optional dependency is available at call time.

    If *package* is not importable, the wrapped function returns a
    standardized error dict instead of raising ``ImportError``.

    Args:
        package: Top-level package name to check (e.g. ``"scipy"``).
        install_hint: Optional ``pip install`` hint for the error message.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if importlib.util.find_spec(package) is None:
                hint = f" {install_hint}" if install_hint else ""
                return {
                    "status": "failed",
                    "error": (
                        f"{package} is not installed.{hint}"
                    ),
                }
            return fn(*args, **kwargs)

        return wrapper

    return decorator
