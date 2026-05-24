"""Goal execution service — unifies SSE and WebSocket streaming.

Eliminates duplicated event limit handling, persistence retry logic,
and orchestration plan emission across ``stream_goal`` (SSE) and
both WebSocket handlers.
"""

import asyncio
import importlib.util
import json
import logging
import os
import tempfile
import time
from typing import Any, AsyncIterator, List, Optional

from uar.core.contracts import GoalSpec
from uar.core.executor import Executor
from uar.core.planner import SimplePlanner
from uar.core.orchestrator import build_orchestration_plan
from uar.core.replay import run_record_from_events
from uar.core.exceptions import EventContractError
from uar.memory.json_store import JsonRunStore
from .base import BaseService
from .events import EventService

# Fast serialization: orjson when available
if importlib.util.find_spec("orjson") is not None:
    import orjson  # type: ignore[import-untyped]

    def _fast_dumps(obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")
else:
    _fast_dumps = json.dumps

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

        # Predictive pre-warming: touch skill cache for upcoming skills
        if os.getenv("UAR_PREDICTIVE_WARM", "true").lower() == "true":
            try:
                from uar.core.skill_cache import get_skill_cache

                cache = get_skill_cache()
                for wave in plan.waves or []:
                    for skill_name in wave:
                        # Pre-warm: compute cache key without running
                        cache_key = cache._make_key(skill_name, "", {})
                        # Touch Redis if backed
                        if hasattr(cache, "_redis"):
                            cache._redis.exists(cache_key)
            except Exception:
                pass

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

        # Buffered write: accumulate lines to amortize syscalls
        _write_buf: list[str] = []
        _write_buf_size = int(os.getenv("UAR_WRITE_BUF_SIZE", "50"))

        def _flush_write_buf() -> None:
            if _write_buf:
                tmp_file.writelines(_write_buf)
                _write_buf.clear()

        try:
            async for raw_event in self._iter_events(
                strategy, goal, timeout, cid
            ):
                event_count += 1
                if event_count >= self.max_stream_events:
                    _write_buf.append(_fast_dumps(raw_event) + "\n")
                    _flush_write_buf()
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
                    _write_buf.append(_fast_dumps(err) + "\n")
                    _flush_write_buf()
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
                    _write_buf.append(_fast_dumps(comp) + "\n")
                    _flush_write_buf()
                    yield comp
                    break

                # Ring buffer eviction
                if len(events) >= self.event_buffer_size:
                    events.pop(0)
                events.append(raw_event)
                _write_buf.append(_fast_dumps(raw_event) + "\n")
                if len(_write_buf) >= _write_buf_size:
                    _flush_write_buf()

                await bp.apply()
                yield raw_event

            _flush_write_buf()
            tmp_file.flush()

            # Persist successful run from temp file
            # Background persistence: fire-and-forget if enabled
            _bg_persist = (
                os.getenv("UAR_BG_PERSIST", "false").lower() == "true"
            )
            if _bg_persist and yield_persisted:
                asyncio.create_task(
                    self._persist_async(
                        tmp_path.name, strategy, user_id, request_id
                    )
                )
                persisted = True
            else:
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

    async def _persist_async(
        self,
        file_path: str,
        strategy: Any,
        user_id: Optional[str],
        request_id: str,
    ) -> None:
        """Background persistence coroutine."""
        await asyncio.get_running_loop().run_in_executor(
            None,
            self._persist_from_file,
            file_path,
            strategy,
            user_id,
            request_id,
        )

    def _persist_from_file(
        self,
        file_path: str,
        strategy: Any,
        user_id: Optional[str],
        request_id: str,
    ) -> Any:
        """Read events from JSONL file (optionally gzip) and persist.

        Optional deduplication (UAR_DEDUP_EVENTS=true) removes exact
        duplicate events that can occur during retries.
        Optional filtering (UAR_PERSIST_FILTER) keeps only specified
        event types, reducing storage 30-50%.
        Uses mmap for large files (>1MB) with sequential readahead.
        """
        events: list[dict] = []
        _dedup = os.getenv("UAR_DEDUP_EVENTS", "false").lower() == "true"
        _filter_env = os.getenv("UAR_PERSIST_FILTER", "")
        _filter_types = set(
            t.strip() for t in _filter_env.split(",") if t.strip()
        )
        seen: set[str] = set()
        try:
            if file_path.endswith(".gz"):
                import gzip

                f = gzip.open(file_path, "rt")
                with f:
                    for line in f:
                        line = line.strip()
                        if line:
                            event = json.loads(line)
                            if _filter_types:
                                if event.get("type") not in _filter_types:
                                    continue
                            if _dedup:
                                ev_hash = json.dumps(
                                    event, sort_keys=True, default=str
                                )
                                if ev_hash in seen:
                                    continue
                                seen.add(ev_hash)
                            events.append(event)
            else:
                # Optional mmap read for large temp files
                _use_mmap = (
                    os.getenv("UAR_MMAP_READ", "true").lower() == "true"
                )
                file_size = os.path.getsize(file_path)
                if _use_mmap and file_size > 1_048_576:  # 1 MB threshold
                    import mmap

                    with open(file_path, "r") as fh:
                        with mmap.mmap(
                            fh.fileno(), 0, access=mmap.ACCESS_READ
                        ) as mm:
                            # Hint kernel for sequential readahead
                            if hasattr(mm, "madvise"):
                                mm.madvise(mmap.MADV_SEQUENTIAL)
                            for line in iter(mm.readline, b""):
                                line_s = line.decode("utf-8").strip()
                                if line_s:
                                    event = json.loads(line_s)
                                    if _filter_types:
                                        et = event.get("type")
                                        if et not in _filter_types:
                                            continue
                                    if _dedup:
                                        ev_hash = json.dumps(
                                            event, sort_keys=True,
                                            default=str,
                                        )
                                        if ev_hash in seen:
                                            continue
                                        seen.add(ev_hash)
                                    events.append(event)
                else:
                    with open(file_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                event = json.loads(line)
                                if _filter_types:
                                    if event.get("type") not in _filter_types:
                                        continue
                                if _dedup:
                                    ev_hash = json.dumps(
                                        event, sort_keys=True, default=str
                                    )
                                    if ev_hash in seen:
                                        continue
                                    seen.add(ev_hash)
                                events.append(event)
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
        Buffers events to amortize thread-switch overhead.
        """
        executor = Executor()
        it = executor.iter_events(
            strategy, goal, timeout_seconds=timeout, correlation_id=cid
        )

        _buf_size = int(os.getenv("UAR_EVENT_BUFFER", "10"))

        def _next_batch() -> List[Optional[dict[str, Any]]]:
            batch: List[Optional[dict[str, Any]]] = []
            for _ in range(_buf_size):
                try:
                    batch.append(next(it))
                except StopIteration:
                    batch.append(None)
                    break
            return batch

        loop = asyncio.get_running_loop()
        while True:
            batch = await loop.run_in_executor(None, _next_batch)
            for event in batch:
                if event is None:
                    return
                yield event
