from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass
class SkillMetadata:
    name: str
    description: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Callable] = {}
        self._metadata: Dict[str, SkillMetadata] = {}

    def register(self, name: str, fn: Callable, metadata: SkillMetadata | None = None):
        self._skills[name] = fn
        self._metadata[name] = metadata or SkillMetadata(name=name)

    def get(self, name: str) -> Callable:
        return self._skills[name]

    def list(self):
        return list(self._skills.keys())

    def metadata(self, name: str) -> SkillMetadata:
        return self._metadata[name]

    def describe(self) -> list[dict[str, Any]]:
        return [self._metadata[name].__dict__ for name in self.list()]


registry = SkillRegistry()


def register_skill(
    name: str,
    description: str = "",
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    tags: list[str] | None = None,
):
    def decorator(fn: Callable):
        registry.register(
            name,
            fn,
            SkillMetadata(
                name=name,
                description=description,
                inputs=inputs or [],
                outputs=outputs or [],
                tags=tags or [],
            ),
        )
        return fn

    return decorator
