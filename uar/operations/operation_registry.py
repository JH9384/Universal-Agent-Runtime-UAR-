from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeOperation:
    operation_id: str
    category: str
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "operation_id": self.operation_id,
            "category": self.category,
            "actions": list(self.actions),
        }


class OperationRegistry:
    def __init__(self) -> None:
        self.operations: Dict[str, RuntimeOperation] = {}

    def register(self, operation: RuntimeOperation) -> None:
        self.operations[operation.operation_id] = operation

    def get(self, operation_id: str) -> RuntimeOperation | None:
        return self.operations.get(operation_id)
