from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from uar.core.contracts import RunRecord


@dataclass
class StructureNode:
    title: str
    kind: str = "section"
    value: Any | None = None
    children: list["StructureNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "kind": self.kind,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
        }


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True)


def _markdown_node(node: StructureNode, depth: int = 1) -> list[str]:
    heading = "#" * min(depth, 6)
    lines = [f"{heading} {node.title}"]
    if node.value not in (None, ""):
        value = _format_value(node.value)
        if "\n" in value:
            lines.extend(["", "```json" if not isinstance(node.value, str) else "```", value, "```"])
        else:
            lines.extend(["", value])
    for child in node.children:
        lines.extend(["", *_markdown_node(child, depth + 1)])
    return lines


def events_to_structure(events: Iterable[dict[str, Any]]) -> StructureNode:
    event_list = list(events)
    root = StructureNode("UAR Run", "run")

    start_event = next((event for event in event_list if event.get("type") == "start"), None)
    complete_event = next((event for event in reversed(event_list) if event.get("type") == "complete"), None)

    if start_event:
        root.children.append(
            StructureNode(
                "Goal",
                "goal",
                start_event.get("payload", {}).get("goal", start_event.get("goal_id")),
            )
        )

    plan_event = next((event for event in event_list if event.get("type") == "orchestration_plan"), None)
    if plan_event:
        graph = plan_event.get("payload", {}).get("graph", {})
        plan_node = StructureNode("Execution Plan", "plan")
        for node in graph.get("nodes", []):
            plan_node.children.append(
                StructureNode(
                    node.get("skill", node.get("id", "skill")),
                    "skill",
                    {"id": node.get("id"), "depends_on": node.get("depends_on", [])},
                )
            )
        root.children.append(plan_node)

    events_node = StructureNode("Events", "events")
    for event in event_list:
        events_node.children.append(
            StructureNode(
                event.get("type", "event"),
                "event",
                {
                    "skill": event.get("skill"),
                    "error": event.get("error"),
                    "payload": event.get("payload", {}),
                },
            )
        )
    root.children.append(events_node)

    if complete_event:
        payload = complete_event.get("payload", {})
        root.children.append(StructureNode("Status", "status", payload.get("status")))
        root.children.append(StructureNode("Outputs", "outputs", payload.get("outputs", [])))
        if payload.get("errors"):
            root.children.append(StructureNode("Errors", "errors", payload.get("errors")))

    return root


def run_record_to_structure(record: RunRecord) -> StructureNode:
    return events_to_structure(record.events)


def structure_to_markdown(root: StructureNode) -> str:
    return "\n".join(_markdown_node(root)).strip() + "\n"


def events_to_markdown(events: Iterable[dict[str, Any]]) -> str:
    return structure_to_markdown(events_to_structure(events))


def run_record_to_markdown(record: RunRecord) -> str:
    return structure_to_markdown(run_record_to_structure(record))
