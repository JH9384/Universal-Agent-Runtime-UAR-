from __future__ import annotations

from typing import Any

from skills import DEFAULT_SKILLS


def plan_for_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []

    for section in sections:
        runtime_markers = section.get("runtime_markers", [])
        numbers = section.get("numbers", [])

        skill = DEFAULT_SKILLS.choose_for_section(
            runtime_markers=runtime_markers,
            numeric_count=len(numbers),
        )

        if not skill:
            continue

        plans.append(
            {
                "section": section.get("label"),
                "skill": skill.name,
                "runtime": skill.runtime,
                "inputs": numbers,
            }
        )

    return plans
