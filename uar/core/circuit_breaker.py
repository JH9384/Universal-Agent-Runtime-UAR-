"""Circuit breaker for external service calls (Ollama, GraphRAG, Autonomi).

States: closed → open → half-open → closed
"""

import time
import threading
import logging
from enum import Enum

from uar.core.exceptions import UARError, ErrorCode

logger = logging.getLogger(__name__)


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max: int = 1,
    ):
        if not name:
            raise ValueError("Circuit breaker name must not be empty")
        if failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be >= 1, got {failure_threshold}"
            )
        if recovery_timeout < 0:
            raise ValueError(
                f"recovery_timeout must be >= 0, got {recovery_timeout}"
            )
        if half_open_max < 1:
            raise ValueError(
                f"half_open_max must be >= 1, got {half_open_max}"
            )
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = State.CLOSED
        self._failures = 0
        self._last_failure_time = time.monotonic()
        self._half_open_count = 0
        self._half_open_successes = 0
        self._generation = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        with self._lock:
            self._transition()
            return self._state

    @property
    def failures(self) -> int:
        with self._lock:
            return self._failures

    @property
    def half_open_count(self) -> int:
        with self._lock:
            return self._half_open_count

    @property
    def half_open_successes(self) -> int:
        with self._lock:
            return self._half_open_successes

    @property
    def last_failure_time(self) -> float:
        with self._lock:
            return self._last_failure_time

    def snapshot(self) -> dict:
        with self._lock:
            self._transition()
            return {
                "state": self._state.value,
                "failures": self._failures,
                "half_open_count": self._half_open_count,
                "half_open_successes": self._half_open_successes,
                "last_failure_time": self._last_failure_time,
            }

    def _transition(self):
        if self._state == State.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = State.HALF_OPEN
                self._half_open_count = 0
                self._half_open_successes = 0
                self._failures = 0
                logger.info(
                    "CircuitBreaker[%s]: open → half_open", self.name
                )

    def call(self, fn, *args, **kwargs):
        # Reserve slot under lock, execute outside lock, update atomically
        reserved_half_open = False
        with self._lock:
            self._transition()
            if self._state == State.OPEN:
                raise CircuitBreakerOpenError(self.name)
            if (
                self._state == State.HALF_OPEN
                and self._half_open_count >= self.half_open_max
            ):
                raise CircuitBreakerOpenError(self.name)

            # Reserve slot for half-open state
            if self._state == State.HALF_OPEN:
                self._half_open_count += 1
                reserved_half_open = True
            _gen = self._generation

        try:
            result = fn(*args, **kwargs)
        except BaseException as _exc:
            with self._lock:
                if self._generation == _gen:
                    if reserved_half_open:
                        self._half_open_count = max(
                            0, self._half_open_count - 1
                        )
                    if isinstance(_exc, Exception):
                        self._failures += 1
                        self._last_failure_time = time.monotonic()
                        if self._state == State.HALF_OPEN:
                            # In half-open, any failure opens
                            # the circuit immediately
                            self._state = State.OPEN
                            logger.warning(
                                "CircuitBreaker[%s]: half_open → open "
                                "(failure in half-open)",
                                self.name,
                            )
                        elif self._failures >= self.failure_threshold:
                            self._state = State.OPEN
                            logger.warning(
                                "CircuitBreaker[%s]: → open (failures=%s)",
                                self.name,
                                self._failures,
                            )
            raise

        with self._lock:
            if self._generation != _gen:
                return result
            if reserved_half_open:
                self._half_open_count = max(0, self._half_open_count - 1)
            self._failures = 0
            if self._state == State.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_max:
                    self._state = State.CLOSED
                    self._half_open_count = 0
                    self._half_open_successes = 0
                    logger.info(
                        "CircuitBreaker[%s]: half_open → closed", self.name
                    )

        return result

    async def call_async(self, fn, *args, **kwargs):
        """Async version of call().

        Reserves a slot under the lock, executes ``await fn(*args, **kwargs)``
        outside the lock, and updates state atomically.
        """
        from uar.core.async_utils import async_lock

        reserved_half_open = False
        async with async_lock(self._lock):
            self._transition()
            if self._state == State.OPEN:
                raise CircuitBreakerOpenError(self.name)
            if (
                self._state == State.HALF_OPEN
                and self._half_open_count >= self.half_open_max
            ):
                raise CircuitBreakerOpenError(self.name)

            # Reserve slot for half-open state
            if self._state == State.HALF_OPEN:
                self._half_open_count += 1
                reserved_half_open = True
            _gen = self._generation

        try:
            result = await fn(*args, **kwargs)
        except BaseException as _exc:
            async with async_lock(self._lock):
                if self._generation == _gen:
                    if reserved_half_open:
                        self._half_open_count = max(
                            0, self._half_open_count - 1
                        )
                    if isinstance(_exc, Exception):
                        self._failures += 1
                        self._last_failure_time = time.monotonic()
                        if self._state == State.HALF_OPEN:
                            # In half-open, any failure opens
                            # the circuit immediately
                            self._state = State.OPEN
                            logger.warning(
                                "CircuitBreaker[%s]: half_open → open "
                                "(failure in half-open)",
                                self.name,
                            )
                        elif self._failures >= self.failure_threshold:
                            self._state = State.OPEN
                            logger.warning(
                                "CircuitBreaker[%s]: → open (failures=%s)",
                                self.name,
                                self._failures,
                            )
            raise

        async with async_lock(self._lock):
            if self._generation != _gen:
                return result
            if reserved_half_open:
                self._half_open_count = max(0, self._half_open_count - 1)
            self._failures = 0
            if self._state == State.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_max:
                    self._state = State.CLOSED
                    self._half_open_count = 0
                    self._half_open_successes = 0
                    logger.info(
                        "CircuitBreaker[%s]: half_open → closed", self.name
                    )

        return result

    def reset(self):
        with self._lock:
            self._generation += 1
            self._state = State.CLOSED
            self._failures = 0
            self._half_open_count = 0
            self._half_open_successes = 0
            self._last_failure_time = time.monotonic()


class CircuitBreakerOpenError(UARError):
    """Raised when circuit breaker is open."""

    code = ErrorCode.EXTERNAL_DOWN

    def __init__(self, name: str):
        self.service_name = name
        super().__init__(f"Circuit breaker open for '{name}'")
