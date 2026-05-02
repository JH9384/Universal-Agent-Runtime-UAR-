from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class Skill:
    name: str
    intent: str
    runtime: str
    input_selector: str
    output_kind: str
    version: str = "0.1.0"
    source: str = "built-in"

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
    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self.skills_dir = Path(skills_dir or Path(__file__).resolve().parent / "skills")
        self._skills: dict[str, Skill] = {SECTION_SUM.name: SECTION_SUM}
        self.load_from_disk()

    def load_from_disk(self) -> None:
        if not self.skills_dir.exists():
            return

        for manifest in sorted(self.skills_dir.glob("*/skill.json")):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            skill = Skill(
                name=str(data["name"]),
                intent=str(data["intent"]),
                runtime=str(data["runtime"]),
                input_selector=str(data["input_selector"]),
                output_kind=str(data["output_kind"]),
                version=str(data.get("version", "0.1.0")),
                source=str(manifest),
            )
            self._skills[skill.name] = skill

    def list(self) -> list[dict[str, Any]]:
        return [skill.to_dict() for skill in self._skills.values()]

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def choose_for_section(self, *, runtime_markers: list[str], numeric_count: int) -> Skill | None:
        normalized = {marker.strip().lower() for marker in runtime_markers}
        if numeric_count > 0 and ("sum" in normalized or "sum_contents" in normalized):
            return self.get("section_sum")
        return None


DEFAULT_SKILLS = SkillRegistry()
