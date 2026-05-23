"""Runtime configuration contract for UAR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlannerMode = Literal["simple", "recipe", "llm"]
PersistenceMode = Literal["jsonl", "sqlite", "memory"]


@dataclass(frozen=True)
class RuntimeConfig:
    """Conservative runtime defaults for deterministic execution."""

    planner_mode: PlannerMode = "simple"
    allow_llm: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    default_timeout_seconds: float = 5.0
    max_event_buffer: int = 10000
    persistence_mode: PersistenceMode = "jsonl"
    stream_enabled: bool = True
    replay_validation_enabled: bool = True

    def validate(self) -> None:
        if self.planner_mode not in {"simple", "recipe", "llm"}:
            raise ValueError(f"Unsupported planner mode: {self.planner_mode!r}")
        if self.planner_mode == "llm" and not self.allow_llm:
            raise ValueError("Adaptive planner requires explicit opt-in")
        if not self.api_host:
            raise ValueError("api_host must be non-empty")
        if not (0 < self.api_port < 65536):
            raise ValueError("api_port must be between 1 and 65535")
        if self.default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        if self.max_event_buffer <= 0:
            raise ValueError("max_event_buffer must be positive")
        if self.persistence_mode not in {"jsonl", "sqlite", "memory"}:
            raise ValueError(f"Unsupported persistence mode: {self.persistence_mode!r}")
