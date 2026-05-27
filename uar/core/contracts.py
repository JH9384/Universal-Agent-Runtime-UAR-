import collections
import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


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
    # Stored as a collections.deque in __post_init__ for O(1) eviction;
    # typed as List for external API compatibility.
    events: List[Dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10000  # Prevent unbounded memory growth
    _overflow_file: Any = field(default=None, repr=False)

    def __post_init__(self):
        # Convert to bounded deque for O(1) oldest-event eviction.
        object.__setattr__(
            self,
            "events",
            collections.deque(self.events, maxlen=self._max_events),
        )
        if os.getenv("UAR_CONTEXT_DISK_OVERFLOW", "").lower() == "true":
            import tempfile

            fd, path = tempfile.mkstemp(suffix=".jsonl")
            os.close(fd)
            object.__setattr__(self, "_overflow_file", open(path, "a"))

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        import json as _json
        event = {"type": event_type, "payload": payload}
        # When overflow is enabled, write the oldest event to disk
        # before the deque drops it (deque evicts oldest automatically).
        if (
            self._overflow_file is not None
            and len(self.events) >= self._max_events
        ):
            oldest = self.events[0]
            self._overflow_file.write(_json.dumps(oldest, default=str))
            self._overflow_file.write("\n")
        # deque with maxlen evicts the oldest entry automatically — O(1).
        self.events.append(event)  # type: ignore[union-attr]

    def close(self) -> None:
        if self._overflow_file is not None:
            self._overflow_file.close()
            object.__setattr__(self, "_overflow_file", None)

    def __del__(self) -> None:
        """Ensure overflow file is closed even if close() is never called."""
        try:
            self.close()
        except Exception:
            logger.warning("PipelineContext cleanup failed", exc_info=True)


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
