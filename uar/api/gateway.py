"""ExecutionGateway — formal API-to-Executor contract boundary.

T5: Protocol Boundaries

The API layer must not reach into uar.core internals directly.
All execution flows go through this gateway, which receives an
API-level RunRequest and returns a core-level RunRecord.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from uar.api.goal_builder import _build_goal
from uar.api.models import RunRequest
from uar.core.contracts import RunRecord

logger = logging.getLogger(__name__)


class ExecutionGateway:
    """Formal boundary between the HTTP API and the execution core.

    Responsibilities:
      1. Translate RunRequest → GoalSpec → StrategySpec → RunRecord
      2. Persist the result to the configured store
      3. Notify side-effect consumers (analytics cache, sync monitor)
      4. Handle idempotency (read-through and write-back)

    The API router should only:
      - Authenticate / authorise
      - Deserialize the RunRequest
      - Call gateway.execute()
      - Serialise the RunRecord into the HTTP response
    """

    def __init__(
        self,
        store: Optional[Any] = None,
        idempotency_get: Optional[Any] = None,
        idempotency_set: Optional[Any] = None,
        analytics_cache: Optional[Any] = None,
        sync_monitor: Optional[Any] = None,
        pool: Optional[Any] = None,
    ) -> None:
        self._store = store
        self._idempotency_get = idempotency_get
        self._idempotency_set = idempotency_set
        self._analytics_cache = analytics_cache
        self._sync_monitor = sync_monitor
        self._pool = pool

    def execute(
        self,
        req: RunRequest,
        *,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RunRecord:
        """Execute a RunRequest and return the resulting RunRecord.

        Args:
            req: Validated API request model.
            user_id: Optional actor identifier (from auth middleware).
            request_id: Optional correlation ID for logging.

        Returns:
            The completed RunRecord (already persisted to store).

        Raises:
            ValidationError: If goal building or planning fails.
            Any exception from Executor.run() is propagated.
        """
        # -- idempotency read-through --
        if req.idempotency_key and self._idempotency_get is not None:
            cached = self._idempotency_get(req.idempotency_key)
            if cached is not None:
                logger.info(
                    "[%s] Idempotency hit: %s",
                    request_id,
                    req.idempotency_key,
                )
                return cached

        # -- build goal & plan --
        goal = _build_goal(req)

        from uar.core.planner import SimplePlanner

        planner = SimplePlanner()
        strategy = planner.plan(goal)

        # -- execute --
        from uar.core.executor import Executor

        executor = Executor(pool=self._pool)
        timeout = req.timeout_seconds or 5.0
        result = executor.run(strategy, goal, timeout_seconds=timeout)
        result.user_id = user_id

        # -- persist --
        if self._store is not None:
            self._store.append(result)
            if hasattr(self._store, "flush"):
                self._store.flush()

        # -- side effects --
        if req.idempotency_key and self._idempotency_set is not None:
            self._idempotency_set(req.idempotency_key, result)

        if self._sync_monitor is not None:
            self._sync_monitor.record_write("default")

        if self._analytics_cache is not None:
            self._analytics_cache.invalidate()

        logger.info(
            "[%s] Run completed: %s",
            request_id,
            result.run_id,
        )
        return result
