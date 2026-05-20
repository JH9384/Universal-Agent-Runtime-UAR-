"""Distributed executor for UAR.

Provides a worker pool abstraction for distributing skill execution
across multiple worker processes or remote nodes.
"""

import concurrent.futures
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .contracts import PipelineContext, RunRecord, StrategySpec
from .exceptions import ValidationError
from .registry import registry

logger = logging.getLogger(__name__)

DEFAULT_POOL_SIZE = int(os.getenv("UAR_DISTRIBUTED_POOL_SIZE", "4"))
DEFAULT_TIMEOUT = float(os.getenv("UAR_DISTRIBUTED_TIMEOUT", "30.0"))


@dataclass
class WorkerTask:
    """A unit of work dispatched to a worker."""

    task_id: str
    skill_name: str
    ctx_data: Dict[str, Any]
    goal_objective: str
    timeout: float = 5.0


@dataclass
class WorkerResult:
    """Result of a worker task execution."""

    task_id: str
    skill_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class WorkerHealth:
    """Health status of a worker."""

    worker_id: str
    last_heartbeat: float
    tasks_completed: int = 0
    tasks_failed: int = 0
    active: bool = True


class WorkerPool:
    """Thread-pool based worker pool for parallel skill execution.

    Uses ``concurrent.futures.ThreadPoolExecutor`` for local parallelism.
    Can be extended to use remote workers via RPC.
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.max_workers = max_workers
        self.timeout = timeout
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        self._health: Dict[str, WorkerHealth] = {}
        self._health_lock = threading.Lock()
        self._task_counter = 0
        self._task_counter_lock = threading.Lock()

    def _next_task_id(self) -> str:
        with self._task_counter_lock:
            self._task_counter += 1
            return f"task-{self._task_counter}-{int(time.time()*1000)}"

    def _execute_task(self, task: WorkerTask) -> WorkerResult:
        """Execute a single task (runs in worker thread)."""
        from .contracts import GoalSpec

        t0 = time.time()
        worker_id = f"worker-{threading.current_thread().name}"
        try:
            if not registry.is_registered(task.skill_name):
                return WorkerResult(
                    task_id=task.task_id,
                    skill_name=task.skill_name,
                    success=False,
                    error=f"Skill '{task.skill_name}' not registered",
                    duration_ms=(time.time() - t0) * 1000,
                )

            goal = GoalSpec(
                id=task.task_id,
                user_intent=task.goal_objective,
                objective=task.goal_objective,
                metadata={},
            )
            ctx = PipelineContext(goal=goal)
            ctx.data.update(task.ctx_data)
            fn = registry.get(task.skill_name)
            result = fn(ctx)
            duration = (time.time() - t0) * 1000

            # Update health
            with self._health_lock:
                h = self._health.setdefault(
                    worker_id,
                    WorkerHealth(
                        worker_id=worker_id,
                        last_heartbeat=time.time(),
                    ),
                )
                h.last_heartbeat = time.time()
                h.tasks_completed += 1

            return WorkerResult(
                task_id=task.task_id,
                skill_name=task.skill_name,
                success=True,
                result=result,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.time() - t0) * 1000
            with self._health_lock:
                h = self._health.setdefault(
                    worker_id,
                    WorkerHealth(
                        worker_id=worker_id,
                        last_heartbeat=time.time(),
                    ),
                )
                h.last_heartbeat = time.time()
                h.tasks_failed += 1

            return WorkerResult(
                task_id=task.task_id,
                skill_name=task.skill_name,
                success=False,
                error=str(exc),
                duration_ms=duration,
            )

    def submit(self, task: WorkerTask) -> concurrent.futures.Future:
        """Submit a task to the pool."""
        self._ensure_executor()
        assert self._executor is not None
        return self._executor.submit(self._execute_task, task)

    def map_tasks(
        self, tasks: List[WorkerTask]
    ) -> List[WorkerResult]:
        """Execute multiple tasks and collect results."""
        if not tasks:
            return []
        self._ensure_executor()
        assert self._executor is not None

        futures = {self.submit(t): t for t in tasks}
        results: List[WorkerResult] = []

        for future in concurrent.futures.as_completed(futures):
            task = futures[future]
            try:
                result = future.result(timeout=self.timeout)
                results.append(result)
            except Exception as exc:
                results.append(
                    WorkerResult(
                        task_id=task.task_id,
                        skill_name=task.skill_name,
                        success=False,
                        error=f"Worker timeout/error: {exc}",
                    )
                )

        return results

    def _ensure_executor(self) -> None:
        with self._lock:
            if self._executor is None or self._executor._shutdown:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="uar-worker",
                )

    def get_health(self) -> Dict[str, Any]:
        """Return health status of all workers."""
        with self._health_lock:
            return {
                w.worker_id: {
                    "active": w.active,
                    "last_heartbeat": w.last_heartbeat,
                    "tasks_completed": w.tasks_completed,
                    "tasks_failed": w.tasks_failed,
                }
                for w in self._health.values()
            }

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=wait)
                self._executor = None


class DistributedExecutor:
    """Executor that distributes skill groups across a worker pool."""

    def __init__(
        self,
        pool: Optional[WorkerPool] = None,
        enable_parallel: bool = True,
    ):
        self.pool = pool or WorkerPool()
        self.enable_parallel = enable_parallel

    def iter_events(
        self,
        strategy: StrategySpec,
        goal,
        timeout_seconds: float = 5.0,
        correlation_id: str = "",
    ):
        """Execute strategy using the worker pool for parallel groups.

        This is a generator-compatible wrapper that yields events
        in the same format as the local Executor. For sequential
        groups it falls back to local execution to preserve the
        event stream ordering.
        """
        # Import local executor for sequential fallback
        from .executor import Executor

        local = Executor()

        if not self.enable_parallel or not strategy.ordered_skills:
            # Fallback to local execution
            yield from local.iter_events(
                strategy,
                goal,
                timeout_seconds=timeout_seconds,
                correlation_id=correlation_id,
            )
            return

        # For now, use the local executor but track that distributed
        # mode is available. Full distributed event streaming would
        # require buffering and reordering events from workers.
        # This implementation provides the infrastructure while
        # maintaining backward compatibility.
        yield from local.iter_events(
            strategy,
            goal,
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id,
        )

    def run(
        self,
        strategy: StrategySpec,
        goal,
        timeout_seconds: float = 5.0,
    ) -> RunRecord:
        """Execute and return a RunRecord."""
        events = list(
            self.iter_events(
                strategy, goal, timeout_seconds=timeout_seconds
            )
        )
        if not events:
            raise ValidationError("No events generated during execution")

        start_event = events[0]
        complete_event = events[-1]
        payload = complete_event.get("payload", {})

        return RunRecord(
            run_id=start_event["run_id"],
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            outputs=payload.get("outputs", []),
            status=payload.get("status", "failed"),
            errors=payload.get("errors", []),
            events=events,
            final_context=payload.get("final_context", {}),
        )

    def execute_skills_parallel(
        self,
        skill_names: List[str],
        goal,
        timeout_seconds: float = 5.0,
    ) -> List[WorkerResult]:
        """Execute a list of skills in parallel via the worker pool.

        This is the primary distributed API — it bypasses the event
        stream and returns aggregated WorkerResults directly.
        """
        tasks = [
            WorkerTask(
                task_id=self.pool._next_task_id(),
                skill_name=sn,
                ctx_data={},
                goal_objective=goal.objective,
                timeout=timeout_seconds,
            )
            for sn in skill_names
        ]
        return self.pool.map_tasks(tasks)


# Global distributed executor instance
_distributed_executor: Optional[DistributedExecutor] = None
_dist_lock = threading.Lock()


def get_distributed_executor() -> DistributedExecutor:
    """Get the global distributed executor (lazy init)."""
    global _distributed_executor
    if _distributed_executor is None:
        with _dist_lock:
            if _distributed_executor is None:
                pool_size = int(
                    os.getenv("UAR_DISTRIBUTED_POOL_SIZE", "4")
                )
                _distributed_executor = DistributedExecutor(
                    pool=WorkerPool(max_workers=pool_size)
                )
    return _distributed_executor
