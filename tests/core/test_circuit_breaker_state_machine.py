"""Circuit breaker state-machine tests.

Pattern borrowed from danielfm/pybreaker.
Tests state transitions, failure thresholds, timeouts, and concurrency.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from uar.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreakerStateMachine:
    """State transition tests (closed → open → half-open → closed)."""

    def test_success_keeps_circuit_closed(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=1)
        assert breaker.call(lambda: "ok") == "ok"
        assert breaker.state.name == "CLOSED"
        assert breaker._failures == 0

    def test_failure_increments_counter_while_closed(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=1)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "CLOSED"
        assert breaker._failures == 1

    def test_success_resets_failure_counter(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=1)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker._failures == 1
        breaker.call(lambda: "ok")
        assert breaker._failures == 0

    def test_threshold_opens_circuit(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "ok")

    def test_open_circuit_raises_on_call(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "ok")

    def test_transitions_to_half_open_after_timeout(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

    def test_half_open_failure_reopens_circuit(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=1
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"

    def test_half_open_success_closes_circuit(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=1
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"
        breaker.call(lambda: "ok")
        assert breaker.state.name == "CLOSED"

    def test_reset_clears_all_state(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"
        breaker.reset()
        assert breaker.state.name == "CLOSED"
        assert breaker._failures == 0
        breaker.call(lambda: "ok")


class TestCircuitBreakerConcurrency:
    """Thread-safety tests."""

    def test_concurrent_failures_open_circuit(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=100, recovery_timeout=60)

        def _fail():
            with pytest.raises(ValueError):
                breaker.call(_raise_error)

        with ThreadPoolExecutor(max_workers=10) as pool:
            for _ in range(100):
                pool.submit(_fail)

        assert breaker.state.name == "OPEN"
        assert breaker._failures == 100

    def test_concurrent_successes_dont_corrupt(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=10, recovery_timeout=60)
        call_count = [0]

        def _succeed():
            breaker.call(lambda: call_count.__setitem__(0, call_count[0] + 1))

        with ThreadPoolExecutor(max_workers=10) as pool:
            for _ in range(100):
                pool.submit(_succeed)

        assert call_count[0] == 100
        assert breaker._failures == 0


class TestCircuitBreakerParameters:
    """Custom parameter tests."""

    def test_custom_failure_threshold(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=5, recovery_timeout=60)
        for _ in range(4):
            with pytest.raises(ValueError):
                breaker.call(_raise_error)
        assert breaker.state.name == "CLOSED"
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"

    def test_custom_recovery_timeout(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.08)
        assert breaker.state.name == "HALF_OPEN"

    def test_custom_half_open_max(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=3
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        # Allow up to 3 calls in half-open
        breaker.call(lambda: "ok")
        breaker.call(lambda: "ok")
        assert breaker.state.name == "HALF_OPEN"
        breaker.call(lambda: "ok")
        assert breaker.state.name == "CLOSED"


def _raise_error():
    raise ValueError("boom")
