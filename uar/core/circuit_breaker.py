"""Circuit breaker for external service calls (Ollama, GraphRAG, Autonomi).

States: closed → open → half-open → closed
"""

import time
import threading
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout: float = 30.0, half_open_max: int = 1):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = State.CLOSED
        self._failures = 0
        self._last_failure_time = 0.0
        self._half_open_count = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        with self._lock:
            self._transition()
            return self._state

    def _transition(self):
        if self._state == State.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = State.HALF_OPEN
                self._half_open_count = 0
                logger.info(f"CircuitBreaker[{self.name}]: open → half_open")

    def call(self, fn, *args, **kwargs):
        with self._lock:
            self._transition()
            if self._state == State.OPEN:
                raise CircuitBreakerOpenError(self.name)
            if self._state == State.HALF_OPEN and self._half_open_count >= self.half_open_max:
                raise CircuitBreakerOpenError(self.name)

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failures += 1
                self._last_failure_time = time.time()
                if self._state == State.HALF_OPEN or self._failures >= self.failure_threshold:
                    self._state = State.OPEN
                    logger.warning(
                        f"CircuitBreaker[{self.name}]: → open "
                        f"(failures={self._failures})"
                    )
            raise

        with self._lock:
            if self._state == State.HALF_OPEN:
                self._half_open_count += 1
            self._failures = 0
            if self._state == State.HALF_OPEN and self._half_open_count >= self.half_open_max:
                self._state = State.CLOSED
                logger.info(f"CircuitBreaker[{self.name}]: half_open → closed")

        return result

    def reset(self):
        with self._lock:
            self._state = State.CLOSED
            self._failures = 0
            self._half_open_count = 0


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Circuit breaker open for '{name}'")
