from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Skill:
    name: str
    intent: str
    runtime: str
    input_selector: str
    output_kind: str
    version: str = "0.1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SECTION_SUM = Skill(
    name="section_sum",
    intent="sum numeric values contained in a parsed document section",
    runtime="sum_contents",
    input_selector="section.number_nodes",
    output_kind="section.result",
)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {SECTION_SUM.name: SECTION_SUM}

    def list(self) -> list[dict[str, Any]]:
        return [skill.to_dict() for skill in self._skills.values()]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def choose_for_section(self, *, runtime_markers: list[str], numeric_count: int) -> Skill | None:
        normalized = {marker.strip().lower() for marker in runtime_markers}
        if numeric_count > 0 and ("sum" in normalized or "sum_contents" in normalized):
            return SECTION_SUM
        return None


DEFAULT_SKILLS = SkillRegistry()
