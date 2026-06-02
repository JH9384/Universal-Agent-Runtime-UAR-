"""Tests for uar.core.circuit_breaker_decorator.

Covers the decorator layer that wraps functions with circuit breaker
protection and exposes global state queries.
"""

import pytest

from uar.core.circuit_breaker_decorator import (
    get_circuit_breaker,
    get_circuit_breaker_states,
    reset_circuit_breaker,
    with_circuit_breaker,
)
from uar.core.exceptions import SkillExecutionError


class TestGetCircuitBreaker:
    def test_creates_instance(self):
        cb = get_circuit_breaker("test_svc_decorator", failure_threshold=2)
        assert cb.name == "test_svc_decorator"
        assert cb.failure_threshold == 2

    def test_reuses_existing(self):
        cb1 = get_circuit_breaker("reuse_me")
        cb2 = get_circuit_breaker("reuse_me")
        assert cb1 is cb2

    def test_different_names_are_independent(self):
        cb_a = get_circuit_breaker("svc_a")
        cb_b = get_circuit_breaker("svc_b")
        assert cb_a is not cb_b


class TestWithCircuitBreaker:
    def test_successful_call(self):
        @with_circuit_breaker("good_svc")
        def reliable():
            return "ok"

        assert reliable() == "ok"

    def test_failure_opens_circuit(self):
        call_count = [0]

        @with_circuit_breaker("bad_svc", failure_threshold=1)
        def flaky():
            call_count[0] += 1
            raise ValueError("boom")

        # First call: circuit closed, raw exception propagates
        with pytest.raises(ValueError, match="boom"):
            flaky()

        # Circuit is now open; second call fails fast with wrapped error
        with pytest.raises(SkillExecutionError, match="Circuit breaker open"):
            flaky()

    def test_open_raises_skill_execution_error(self):
        @with_circuit_breaker("err_svc", failure_threshold=1)
        def always_fail():
            raise RuntimeError("fail")

        # First call: circuit closed, raw exception propagates
        with pytest.raises(RuntimeError, match="fail"):
            always_fail()

        # Second call: circuit open, wrapped as SkillExecutionError
        with pytest.raises(SkillExecutionError, match="Circuit breaker open"):
            always_fail()

    def test_passes_through_args_and_kwargs(self):
        @with_circuit_breaker("echo_svc")
        def echo(a, b, c=None):
            return (a, b, c)

        assert echo(1, 2, c=3) == (1, 2, 3)


class TestResetCircuitBreaker:
    def test_reset_closes_circuit(self):
        @with_circuit_breaker("reset_me", failure_threshold=1)
        def fail_once():
            raise ValueError("x")

        # First call: circuit closed, raw exception
        with pytest.raises(ValueError, match="x"):
            fail_once()

        assert get_circuit_breaker_states()["reset_me"] == "open"

        # Reset and call again
        reset_circuit_breaker("reset_me")
        assert get_circuit_breaker_states()["reset_me"] == "closed"

        # After reset, circuit is closed so raw exception propagates again
        with pytest.raises(ValueError, match="x"):
            fail_once()

    def test_reset_unknown_no_error(self):
        reset_circuit_breaker("nonexistent")  # no error


class TestGetCircuitBreakerStates:
    def test_returns_current_states(self):
        get_circuit_breaker("stateful")
        states = get_circuit_breaker_states()
        assert "stateful" in states
        assert states["stateful"] == "closed"

    def test_empty_when_no_breakers(self):
        # This is global state; we can only assert it returns a dict
        states = get_circuit_breaker_states()
        assert isinstance(states, dict)


class TestRegistryThreadSafety:
    def test_concurrent_states_and_registration(self):
        """Regression: get_circuit_breaker_states must hold registry lock.

        Without the lock, concurrent mutation (get_circuit_breaker creating
        new entries) causes RuntimeError: dictionary changed size during
        iteration inside the dict comprehension.
        """
        import threading
        import time

        errors = []
        stop = threading.Event()

        def mutator():
            for i in range(500):
                get_circuit_breaker(f"concurrent_test_{i}")
                time.sleep(0.0001)

        def reader():
            try:
                while not stop.is_set():
                    get_circuit_breaker_states()
                    time.sleep(0.0001)
            except Exception as exc:
                errors.append(exc)

        mutator_thread = threading.Thread(target=mutator)
        reader_threads = [threading.Thread(target=reader) for _ in range(3)]

        for t in reader_threads:
            t.start()
        mutator_thread.start()

        mutator_thread.join(timeout=5)
        stop.set()
        for t in reader_threads:
            t.join(timeout=2)

        assert not errors, f"Thread-safety regression: {errors}"

    def test_concurrent_reset_and_registration(self):
        """Regression: reset_circuit_breaker must hold registry lock."""
        import threading
        import time

        errors = []

        # Pre-populate
        for i in range(50):
            get_circuit_breaker(f"reset_test_{i}")

        def resetter():
            for i in range(500):
                reset_circuit_breaker(f"reset_test_{i % 50}")
                time.sleep(0.0001)

        def creator():
            try:
                for i in range(500):
                    get_circuit_breaker(f"reset_new_{i}")
                    time.sleep(0.0001)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=resetter)
        t2 = threading.Thread(target=creator)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread-safety regression: {errors}"
