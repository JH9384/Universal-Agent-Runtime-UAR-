"""Goal execution service — unifies SSE and WebSocket streaming.

Eliminates duplicated event limit handling, persistence retry logic,
and orchestration plan emission across ``stream_goal`` (SSE) and
both WebSocket handlers.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from typing import Any, AsyncIterator, Optional

from uar.core.contracts import GoalSpec
from uar.core.executor import Executor
from uar.core.planner import SimplePlanner
from uar.core.orchestrator import build_orchestration_plan
from uar.core.replay import run_record_from_events
from uar.core.exceptions import EventContractError
from uar.memory.json_store import JsonRunStore
from .base import BaseService
from .events import EventService

logger = logging.getLogger(__name__)

# Streaming bounds (module defaults; overridable per-instance)
_MAX_STREAM_EVENTS = int(os.getenv("MAX_STREAM_EVENTS", "5000"))
_EVENT_BUFFER_SIZE = int(os.getenv("EVENT_BUFFER_SIZE", "200"))
BACKPRESSURE_ENABLED = (
    os.getenv("BACKPRESSURE_ENABLED", "true").lower() == "true"
)


class AdaptiveBackpressure:
    """Adjusts event emission delay based on client consumption rate."""

    def __init__(
        self,
        enabled: bool = True,
        max_delay: float = 1.0,
        min_delay: float = 0.0,
        slow_threshold: float = 0.5,
        fast_threshold: float = 0.1,
        increment: float = 0.05,
        decrement: float = 0.02,
    ) -> None:
        self.enabled = enabled
        self.max_delay = max_delay
        self.min_delay = min_delay
        self.slow_threshold = slow_threshold
        self.fast_threshold = fast_threshold
        self.increment = increment
        self.decrement = decrement
        self._current_delay = 0.0
        self._last_emit_time = 0.0

    async def apply(self) -> None:
        if not self.enabled:
            return
        now = time.time()
        if self._last_emit_time > 0:
            emit_duration = now - self._last_emit_time
            if emit_duration > self.slow_threshold:
                self._current_delay = min(
                    self._current_delay + self.increment,
                    self.max_delay,
                )
            elif emit_duration < self.fast_threshold:
                self._current_delay = max(
                    self._current_delay - self.decrement,
                    self.min_delay,
                )
            if self._current_delay > 0:
                await asyncio.sleep(self._current_delay)
        self._last_emit_time = time.time()


class GoalExecutionService(BaseService):
    """Execute goals with unified streaming for SSE and WebSocket."""

    def __init__(
        self,
        event_service: Optional[EventService] = None,
        store: Optional[JsonRunStore] = None,
        max_stream_events: int = _MAX_STREAM_EVENTS,
        event_buffer_size: int = _EVENT_BUFFER_SIZE,
        **deps: Any,
    ) -> None:
        super().__init__(**deps)
        self._event = event_service or EventService()
        self._store = store or JsonRunStore()
        self.max_stream_events = max_stream_events
        self.event_buffer_size = event_buffer_size

    async def stream_goal(
        self,
        goal: GoalSpec,
        request_id: str,
        user_id: Optional[str],
        correlation_id: str,
        yield_persisted: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events for a goal execution ( consumed by SSE / WS ).

        Encapsulates:
        - Strategy planning
        - Orchestration graph emission
        - Executor iteration
        - Event limit enforcement
        - Adaptive backpressure
        - Persistence on completion
        """
        strategy = SimplePlanner().plan(goal)
        # Check for explicit skill dependencies in goal metadata
        dependency_map = goal.metadata.get("skill_dependencies")
        plan = build_orchestration_plan(strategy, dependency_map)
        # Inject waves into strategy so executor can use them
        strategy.waves = plan.waves
        timeout = goal.metadata.get("timeout_seconds", 5.0)
        cid = correlation_id
        gid = strategy.goal_id

        # Emit orchestration plan first
        yield self._event.orchestration_plan(
            graph=plan.to_graph(),
            run_id="pending",
            goal_id=gid,
            correlation_id=cid,
        )

        bp = AdaptiveBackpressure(enabled=BACKPRESSURE_ENABLED)
        events: list[dict] = []
        persisted = False
        event_count = 0

        # Stream events to a temp file instead of buffering in memory.
        # This prevents unbounded memory growth for long executions.
        _gzip_events = os.getenv("UAR_GZIP_EVENTS", "false").lower() == "true"
        suffix = ".jsonl.gz" if _gzip_events else ".jsonl"
        tmp_path = tempfile.NamedTemporaryFile(
            mode="wb" if _gzip_events else "w",
            suffix=suffix,
            delete=False,
        )
        tmp_path.close()
        if _gzip_events:
            import gzip

            tmp_file = gzip.open(tmp_path.name, "at")
        else:
            tmp_file = open(tmp_path.name, "a")

        try:
            async for raw_event in self._iter_events(
                strategy, goal, timeout, cid
            ):
                event_count += 1
                if event_count >= self.max_stream_events:
                    tmp_file.write(json.dumps(raw_event, default=str) + "\n")
                    err = self._event.error(
                        run_id="unknown",
                        error_msg=(
                            f"Event limit reached ({self.max_stream_events})."
                        ),
                        code="EVENT_LIMIT",
                        request_id=request_id,
                        goal_id=gid,
                        correlation_id=cid,
                    )
                    tmp_file.write(json.dumps(err, default=str) + "\n")
                    yield err
                    comp = self._event.complete(
                        run_id="unknown",
                        status="failed",
                        errors=[
                            f"Event limit reached ({self.max_stream_events})"
                        ],
                        goal_id=gid,
                        correlation_id=cid,
                    )
                    tmp_file.write(json.dumps(comp, default=str) + "\n")
                    yield comp
                    break

                # Ring buffer eviction
                if len(events) >= self.event_buffer_size:
                    events.pop(0)
                events.append(raw_event)
                tmp_file.write(json.dumps(raw_event, default=str) + "\n")

                await bp.apply()
                yield raw_event

            tmp_file.flush()

            # Persist successful run from temp file
            record = self._persist_from_file(
                tmp_path.name, strategy, user_id, request_id
            )
            persisted = True
            if yield_persisted and record is not None:
                yield self._event.create(
                    "persisted",
                    run_id=record.run_id,
                    goal_id=gid,
                    correlation_id=cid,
                    payload={"run_id": record.run_id},
                )

        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            self._log("error", f"Stream error: {exc}", request_id)
            err = self._event.error(
                run_id="unknown",
                error_msg=str(exc),
                code="EXECUTION_ERROR",
                request_id=request_id,
                goal_id=gid,
                correlation_id=cid,
            )
            yield err
            raise
        finally:
            tmp_file.close()
            if not persisted:
                try:
                    self._persist_from_file(
                        tmp_path.name, strategy, user_id, request_id
                    )
                except Exception as persist_err:
                    self._log(
                        "error",
                        f"Fallback persistence failed: {persist_err}",
                        request_id,
                    )
            try:
                os.unlink(tmp_path.name)
            except Exception:
                pass

    def _persist(
        self,
        events: list[dict],
        strategy: Any,
        user_id: Optional[str],
        request_id: str,
    ) -> Any:
        """Persist run record from events. Returns the record or None."""
        try:
            record = run_record_from_events(
                events, strategy.ordered_skills, user_id
            )
            self._store.append(record)
            self._log(
                "info",
                f"Stream persisted: {record.run_id}",
                request_id,
            )
            return record
        except EventContractError:
            # Deterministic errors shouldn't trigger retry
            self._log(
                "warning",
                "Persistence skipped: contract error",
                request_id,
            )
            return None
        except Exception as persist_error:
            self._log(
                "error",
                f"Failed to persist: {persist_error}",
                request_id,
            )
            return None

    def _persist_from_file(
        self,
        file_path: str,
        strategy: Any,
        user_id: Optional[str],
        request_id: str,
    ) -> Any:
        """Read events from JSONL file (optionally gzip) and persist."""
        events: list[dict] = []
        try:
            if file_path.endswith(".gz"):
                import gzip

                f = gzip.open(file_path, "rt")
            else:
                f = open(file_path, "r")
            with f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as read_err:
            self._log(
                "error",
                f"Failed to read event file: {read_err}",
                request_id,
            )
            return None
        return self._persist(events, strategy, user_id, request_id)

    async def _iter_events(
        self,
        strategy: Any,
        goal: GoalSpec,
        timeout: float,
        cid: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Bridge sync Executor.iter_events into async stream.

        Owns the Executor lifecycle so callers don't need to manage it.
        """
        executor = Executor()
        it = executor.iter_events(
            strategy, goal, timeout_seconds=timeout, correlation_id=cid
        )

        def _next() -> Optional[dict[str, Any]]:
            try:
                return next(it)
            except StopIteration:
                return None

        loop = asyncio.get_running_loop()
        while True:
            event = await loop.run_in_executor(None, _next)
            if event is None:
                break
            yield event
