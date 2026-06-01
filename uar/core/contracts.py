import atexit
import collections
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Module-level registry of overflow file paths for guaranteed cleanup
# even when __del__ is skipped (circular refs, interpreter shutdown).
_overflow_paths: Set[str] = set()
_overflow_init_lock = threading.Lock()


def _cleanup_overflow_file(path: str) -> None:
    """Remove the overflow file created by PipelineContext."""
    try:
        os.unlink(path)
    except Exception:
        pass
    with _overflow_init_lock:
        _overflow_paths.discard(path)


def _cleanup_all_overflow_files() -> None:
    """atexit handler: remove any remaining overflow files."""
    for path in list(_overflow_paths):
        _cleanup_overflow_file(path)


atexit.register(_cleanup_all_overflow_files)


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
    # Stored as a collections.deque in __post_init__ for O(1) eviction.
    events: Deque[Dict[str, Any]] = field(default_factory=list)
    _max_events: int = 10000  # Prevent unbounded memory growth
    _overflow_file: Any = field(default=None, repr=False)
    _overflow_lock: Any = field(default=None, repr=False)
    # When None (default) the env var UAR_CONTEXT_DISK_OVERFLOW is
    # consulted.  Explicit True/False overrides the env var so callers
    # (e.g. parallel skill copies) can disable overflow without
    # mutating process-global os.environ.
    _enable_disk_overflow: Optional[bool] = field(default=None, repr=False)

    def __post_init__(self):
        # Convert to bounded deque for O(1) oldest-event eviction.
        object.__setattr__(
            self,
            "events",
            collections.deque(self.events, maxlen=self._max_events),
        )
        # Always create the lock so emit() never needs a race-prone
        # lazy-init path.
        object.__setattr__(self, "_overflow_lock", threading.Lock())
        # Use the explicit field when set, otherwise fall back to the
        # env var for backward compatibility.
        if self._enable_disk_overflow is None:
            enable_overflow = (
                os.getenv("UAR_CONTEXT_DISK_OVERFLOW", "").lower() == "true"
            )
        else:
            enable_overflow = self._enable_disk_overflow
        if enable_overflow:
            import tempfile

            fd, path = tempfile.mkstemp(suffix=".jsonl")
            os.close(fd)
            try:
                _file = open(path, "a")
                object.__setattr__(self, "_overflow_file", _file)
            finally:
                # Track the path in the module-level registry so atexit
                # can clean it up even if __del__ is never called.
                with _overflow_init_lock:
                    _overflow_paths.add(path)

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        import json as _json
        event = {"type": event_type, "payload": payload}
        # When overflow is enabled, write the oldest event to disk
        # before the deque drops it (deque evicts oldest automatically).
        # Protected by _overflow_lock so concurrent emit() calls cannot
        # read the wrong oldest event between the len check and append.
        lock = self._overflow_lock
        # _overflow_lock is always initialised in __post_init__;
        # this guard is defensive against pathological setattr.
        if lock is None:
            lock = threading.Lock()
            object.__setattr__(self, "_overflow_lock", lock)
        with lock:
            # Re-verify inside the lock: another thread may have called
            # close() between the outer check and lock acquisition.
            if self._overflow_file is not None:
                if len(self.events) >= self._max_events:
                    oldest = self.events[0]
                    self._overflow_file.write(_json.dumps(oldest, default=str))
                    self._overflow_file.write("\n")
                    try:
                        self._overflow_file.flush()
                    except OSError:
                        # Disk full / read-only filesystem — degrade
                        # gracefully rather than crashing the skill.
                        pass
            # deque maxlen evicts oldest automatically — O(1).
            self.events.append(event)  # type: ignore[union-attr]

    def close(self) -> None:
        # Acquire the lock so close() is atomic with emit().
        lock = self._overflow_lock
        if lock is None:
            lock = threading.Lock()
            object.__setattr__(self, "_overflow_lock", lock)
        with lock:
            if self._overflow_file is not None:
                _path = self._overflow_file.name
                try:
                    self._overflow_file.close()
                except Exception:
                    pass
                object.__setattr__(self, "_overflow_file", None)
                try:
                    _cleanup_overflow_file(_path)
                except Exception:
                    pass

    def __del__(self) -> None:
        """Best-effort cleanup; avoids module-global references that may
        be ``None`` during interpreter shutdown.

        Uses a *non-blocking* lock acquire so that if the same thread
        already holds the lock (e.g. GC triggered inside ``emit()``)
        we skip rather than deadlock on a non-reentrant Lock.
        """
        try:
            lock = self._overflow_lock
            if lock is not None and threading is not None:
                # Non-blocking: if another call on this thread holds
                # the lock, skip rather than deadlock.
                if lock.acquire(blocking=False):
                    try:
                        _f = self._overflow_file
                        if _f is not None:
                            object.__setattr__(self, "_overflow_file", None)
                            _n = _f.name
                            try:
                                _f.close()
                            except Exception:
                                pass
                            try:
                                _cleanup_overflow_file(_n)
                            except Exception:
                                pass
                    finally:
                        try:
                            lock.release()
                        except Exception:
                            pass
            else:
                _f = self._overflow_file
                if _f is not None:
                    try:
                        _f.close()
                    except Exception:
                        pass
                    try:
                        _cleanup_overflow_file(_f.name)
                    except Exception:
                        pass
        except Exception:
            pass


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
    metadata: Dict[str, Any] = field(default_factory=dict)
