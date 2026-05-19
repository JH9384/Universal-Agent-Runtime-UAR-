from typing import Callable, Dict, List
from functools import lru_cache

from .exceptions import SkillNotFoundError, ValidationError


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        """Register a skill with validation"""
        if not name or not isinstance(name, str):
            raise ValidationError(
                "Skill name must be a non-empty string", field="name"
            )

        if not callable(fn):
            raise ValidationError(
                "Skill function must be callable", field="function"
            )

        if name in self._skills:
            raise ValidationError(
                f"Skill '{name}' is already registered", field="name"
            )

        self._skills[name] = fn

    def get(self, name: str) -> Callable:
        """Get a skill with proper error handling"""
        if name not in self._skills:
            raise SkillNotFoundError(name)
        return self._skills[name]

    @lru_cache(maxsize=1)
    def list(self) -> List[str]:
        """List all registered skills (cached)"""
        return list(self._skills.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a skill is registered"""
        return name in self._skills


registry = SkillRegistry()


def register_skill(name: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        registry.register(name, fn)
        return fn

    return decorator
