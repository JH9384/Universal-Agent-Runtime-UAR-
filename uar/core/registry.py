from __future__ import annotations

import atexit
import importlib.util
import threading
from typing import Any, Callable, Dict, List
from functools import wraps

from .exceptions import SkillNotFoundError, ValidationError


class _SkillTrie:
    """Simple prefix trie for fast skill name prefix matching."""

    def __init__(self) -> None:
        self._root: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def add(self, name: str) -> None:
        with self._lock:
            node = self._root
            for ch in name:
                if ch not in node:
                    node[ch] = {}
                node = node[ch]
            node["__end__"] = True

    def remove(self, name: str) -> None:
        with self._lock:
            # Simple removal — not fully cleaning empty branches
            node = self._root
            for ch in name:
                if ch not in node:
                    return
                node = node[ch]
            node.pop("__end__", None)

    def prefix_matches(self, prefix: str) -> List[str]:
        """Return all skill names that start with *prefix*."""
        with self._lock:
            node = self._root
            for ch in prefix:
                if ch not in node:
                    return []
                node = node[ch]
            results: List[str] = []
            self._collect(node, prefix, results)
            return results

    def _collect(
        self, node: Dict[str, Any], prefix: str, out: List[str]
    ) -> None:
        if "__end__" in node:
            out.append(prefix)
        for ch, child in node.items():
            if ch != "__end__":
                self._collect(child, prefix + ch, out)


class SkillRegistry:
    """Thread-safe registry of named pipeline skills.

    Registration is idempotent failure (raises on duplicate names) and
    listing returns a snapshot — no caching, because the previous
    ``@lru_cache`` decorator on a bound method silently returned a
    stale list whenever new skills were registered after the first
    call.

    Supports lazy loading: skills can be registered as module paths
    (e.g. ``"uar.skills.math"``) and are imported on first ``get()``.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Callable] = {}
        self._lazy: Dict[str, str] = {}  # name -> module_path
        self._lock = threading.RLock()
        self._session: Any = None
        self._plugins_loaded = False
        self._trie = _SkillTrie()

    def register(self, name: str, fn: Callable) -> None:
        """Register a skill with validation.

        ``fn`` may be a callable or a module path string for lazy
        loading (e.g. ``"uar.skills.math:compute"``).
        """
        if not name or not isinstance(name, str):
            raise ValidationError(
                "Skill name must be a non-empty string", field="name"
            )

        with self._lock:
            if name in self._skills or name in self._lazy:
                raise ValidationError(
                    f"Skill '{name}' is already registered", field="name"
                )
            if isinstance(fn, str):
                if not fn.strip() or any(ch.isspace() for ch in fn):
                    raise ValidationError(
                        "Lazy skill path must be a valid module path",
                        field="function",
                    )
                self._lazy[name] = fn
                self._trie.add(name)
            elif callable(fn):
                self._skills[name] = fn
                self._trie.add(name)
            else:
                raise ValidationError(
                    "Skill function must be callable or a module path",
                    field="function",
                )

    def _lazy_load_plugins(self) -> None:
        """Load external plugins on first skill miss."""
        if self._plugins_loaded:
            return
        with self._lock:
            if self._plugins_loaded:
                return
            self._plugins_loaded = True
        try:
            from uar.skills.plugin import load_plugins

            load_plugins()
        except Exception:
            pass

    def _get_session(self) -> Any:
        """Lazy shared HTTP session with connection pooling."""
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            try:
                import requests

                self._session = requests.Session()
                atexit.register(self._close_session)
            except Exception:
                self._session = None
            return self._session

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def _resolve_lazy(self, name: str) -> None:
        """Import and bind a lazily registered skill."""
        import importlib

        from uar.core.skill_cache import _compiled_skill_cache

        path = self._lazy.get(name, "")
        if not path:
            return
        # Check compiled skill cache first
        cached = _compiled_skill_cache.get(path)
        if cached is not None:
            self._skills[name] = cached
            del self._lazy[name]
            return
        try:
            if ":" in path:
                mod_path, attr = path.rsplit(":", 1)
                mod = importlib.import_module(mod_path)
                fn = getattr(mod, attr)
            else:
                mod = importlib.import_module(path)
                fn = getattr(mod, name.replace("-", "_"), None)
                if fn is None:
                    # Try common entry-point names
                    fn = getattr(mod, "run", None)
            if callable(fn):
                self._skills[name] = fn
                _compiled_skill_cache.set(path, fn)
            del self._lazy[name]
        except Exception:
            pass

    def get(self, name: str) -> Callable:
        """Look up a registered skill by name."""
        with self._lock:
            fn = self._skills.get(name)
            if fn is None and name in self._lazy:
                self._resolve_lazy(name)
                fn = self._skills.get(name)
        if fn is None:
            self._lazy_load_plugins()
            with self._lock:
                fn = self._skills.get(name)
                if fn is None and name in self._lazy:
                    self._resolve_lazy(name)
                    fn = self._skills.get(name)
        if fn is None:
            raise SkillNotFoundError(name)
        return fn

    def list(self) -> List[str]:
        """Return a sorted snapshot of registered skill names."""
        with self._lock:
            return sorted(self._skills.keys())

    def is_registered(self, name: str) -> bool:
        """Return whether ``name`` is registered (resolved or lazy)."""
        with self._lock:
            return name in self._skills or name in self._lazy

    def search_by_prefix(self, prefix: str) -> List[str]:
        """Return skill names starting with *prefix* (trie-backed)."""
        return self._trie.prefix_matches(prefix)


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
