from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any


def parse_skill_md(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")

    name_match = re.search(r"name\s*\|\s*(.+)", text)
    desc_match = re.search(r"description\s*\|\s*(.+)", text)

    name = name_match.group(1).strip() if name_match else path.parent.name
    description = desc_match.group(1).strip() if desc_match else "Imported skill"

    trigger_match = re.search(r"Trigger:(.*?)\n\n", text, re.S)
    trigger = trigger_match.group(1).strip() if trigger_match else ""

    return {
        "name": name,
        "description": description,
        "trigger": trigger,
        "raw": text[:2000],
    }


def convert_to_template(skill: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": skill["name"].lower().replace(" ", "_"),
        "name": skill["name"],
        "description": skill["description"],
        "goal_template": skill["description"],
        "skills": [],
        "required_inputs": [],
        "planner": "llm",
    }


def load_skill_directory(path: str) -> list[Dict[str, Any]]:
    base = Path(path)
    templates = []

    for skill_file in base.glob("**/SKILL.md"):
        parsed = parse_skill_md(skill_file)
        templates.append(convert_to_template(parsed))

    return templates
