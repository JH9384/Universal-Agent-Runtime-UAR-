from __future__ import annotations

import importlib.util
import threading
from typing import Any, Callable, Dict, List, Optional
from functools import wraps

from .contracts import SkillContract
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
            node = self._root
            for ch in name:
                if ch not in node:
                    return
                node = node[ch]
            node.pop("__end__", None)

    def prefix_matches(self, prefix: str) -> List[str]:
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

    Phase 2A/2B adds optional SkillContract governance metadata. Skills
    without explicit contracts receive a conservative default contract so
    existing registrations remain backward-compatible while enforcement can
    be tightened incrementally.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Callable] = {}
        self._lazy: Dict[str, str] = {}
        self._contracts: Dict[str, SkillContract] = {}
        self._lock = threading.RLock()
        self._session: Any = None
        self._plugins_loaded = False
        self._trie = _SkillTrie()

    def register(
        self,
        name: str,
        fn: Callable,
        contract: Optional[SkillContract] = None,
    ) -> None:
        """Register a skill with validation and optional contract metadata."""
        if not name or not isinstance(name, str):
            raise ValidationError(
                "Skill name must be a non-empty string", field="name"
            )

        skill_contract = contract or SkillContract(name=name)
        if skill_contract.name != name:
            raise ValidationError(
                "SkillContract.name must match registered skill name",
                field="contract.name",
            )
        contract_errors = skill_contract.validate()
        if contract_errors:
            raise ValidationError(
                "; ".join(contract_errors), field="contract"
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
                self._contracts[name] = skill_contract
                self._trie.add(name)
            elif callable(fn):
                self._skills[name] = fn
                self._contracts[name] = skill_contract
                self._trie.add(name)
            else:
                raise ValidationError(
                    "Skill function must be callable or a module path",
                    field="function",
                )

    def register_contract(self, contract: SkillContract) -> None:
        """Attach or replace governance metadata for an existing skill."""
        errors = contract.validate()
        if errors:
            raise ValidationError("; ".join(errors), field="contract")
        with self._lock:
            if contract.name not in self._skills and contract.name not in self._lazy:
                raise SkillNotFoundError(contract.name)
            self._contracts[contract.name] = contract

    def get_contract(self, name: str) -> SkillContract:
        """Return governance contract for a skill.

        A conservative default is returned if a legacy skill lacks an explicit
        contract. The default is experimental and ReplayConditional.
        """
        with self._lock:
            if name not in self._skills and name not in self._lazy:
                raise SkillNotFoundError(name)
            contract = self._contracts.get(name)
            if contract is None:
                contract = SkillContract(name=name)
                self._contracts[name] = contract
            return contract

    def validate_contract(self, name: str) -> List[str]:
        """Validate a registered skill contract."""
        return self.get_contract(name).validate()

    def list_by_maturity(self, maturity: str) -> List[str]:
        """Return registered skills matching a maturity class."""
        with self._lock:
            names = set(self._skills) | set(self._lazy)
            return sorted(
                name for name in names
                if self.get_contract(name).maturity == maturity
            )

    def list_replay_safe(self) -> List[str]:
        """Return skills declared ReplaySafe."""
        with self._lock:
            names = set(self._skills) | set(self._lazy)
            return sorted(
                name for name in names
                if self.get_contract(name).replay_safety == "ReplaySafe"
            )

    def list_side_effecting(self) -> List[str]:
        """Return skills that are not PURE."""
        with self._lock:
            names = set(self._skills) | set(self._lazy)
            return sorted(
                name for name in names
                if self.get_contract(name).side_effect_policy != "PURE"
            )

    def list_contract_violations(self) -> Dict[str, List[str]]:
        """Return all registered skills with invalid contract metadata."""
        with self._lock:
            names = set(self._skills) | set(self._lazy)
            violations: Dict[str, List[str]] = {}
            for name in sorted(names):
                errors = self.get_contract(name).validate()
                if errors:
                    violations[name] = errors
            return violations

    def _lazy_load_plugins(self) -> None:
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
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            try:
                import requests

                self._session = requests.Session()
            except Exception:
                self._session = None
            return self._session

    def _resolve_lazy(self, name: str) -> None:
        import importlib

        from uar.core.skill_cache import _compiled_skill_cache

        path = self._lazy.get(name, "")
        if not path:
            return
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
                    fn = getattr(mod, "run", None)
            if callable(fn):
                self._skills[name] = fn
                _compiled_skill_cache.set(path, fn)
            del self._lazy[name]
        except Exception:
            pass

    def get(self, name: str) -> Callable:
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
        with self._lock:
            return sorted(self._skills.keys())

    def is_registered(self, name: str) -> bool:
        with self._lock:
            return name in self._skills

    def search_by_prefix(self, prefix: str) -> List[str]:
        return self._trie.prefix_matches(prefix)


registry = SkillRegistry()


def register_skill(
    name: str,
    contract: Optional[SkillContract] = None,
) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        registry.register(name, fn, contract=contract)
        return fn

    return decorator


def requires_package(
    package: str, *, install_hint: str = ""
) -> Callable[[Callable], Callable]:
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
