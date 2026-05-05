from dataclasses import dataclass, field
from typing import List, Dict, Any


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


@dataclass
class PipelineContext:
    goal: GoalSpec
    data: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10000  # Prevent unbounded memory growth

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        # Circular buffer: drop oldest events when limit reached
        if len(self.events) >= self._max_events:
            self.events.pop(0)  # Remove oldest
        self.events.append({"type": event_type, "payload": payload})


@dataclass
class RunRecord:
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List[Any] = field(default_factory=list)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    final_context: Dict[str, Any] = field(default_factory=dict)
