from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeBootstrapStep:
    name: str
    command: str
    required: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "required": self.required,
        }


@dataclass(slots=True)
class RuntimeBootstrapPlan:
    environment: str
    steps: List[RuntimeBootstrapStep] = field(default_factory=list)

    def add_step(self, step: RuntimeBootstrapStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> Dict[str, object]:
        return {
            "environment": self.environment,
            "steps": [step.to_dict() for step in self.steps],
        }
