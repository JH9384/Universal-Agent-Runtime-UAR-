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


@dataclass
class StrategySpec:
    goal_id: str
    ordered_skills: List[str]


@dataclass
class RunRecord:
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List[Any] = field(default_factory=list)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
