from typing import Callable, Dict


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable):
        self._skills[name] = fn

    def get(self, name: str) -> Callable:
        return self._skills[name]

    def list(self):
        return list(self._skills.keys())


registry = SkillRegistry()


def register_skill(name: str):
    def decorator(fn: Callable):
        registry.register(name, fn)
        return fn

    return decorator
