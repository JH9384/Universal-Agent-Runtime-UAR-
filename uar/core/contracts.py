import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class GoalSpec:
    id: str
    user_intent: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySpec:
    goal_id: str
    ordered_skills: List[str]
    waves: Optional[List[List[str]]] = None


@dataclass(slots=True)
class PipelineContext:
    goal: GoalSpec
    data: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10000  # Prevent unbounded memory growth
    _overflow_file: Any = field(default=None, repr=False)

    def __post_init__(self):
        if os.getenv("UAR_CONTEXT_DISK_OVERFLOW", "").lower() == "true":
            import tempfile

            fd, path = tempfile.mkstemp(suffix=".jsonl")
            os.close(fd)
            object.__setattr__(self, "_overflow_file", open(path, "a"))

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        # Circular buffer: drop oldest events when limit reached
        if len(self.events) >= self._max_events:
            if self._overflow_file is not None:
                import json

                self._overflow_file.write(json.dumps(event, default=str))
                self._overflow_file.write("\n")
            else:
                self.events.pop(0)  # Remove oldest
        self.events.append(event)

    def close(self) -> None:
        if self._overflow_file is not None:
            self._overflow_file.close()
            self._overflow_file = None


@dataclass(slots=True)
class RunRecord:
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List[Any] = field(default_factory=list)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    final_context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    uor_address: Optional[str] = None
    uor_witness: Optional[Dict[str, Any]] = None
