"""Tests for production hardening features."""

from uar.core.circuit_breaker import CircuitBreaker, State
from uar.core.circuit_breaker_decorator import (
    get_circuit_breaker,
    get_circuit_breaker_states,
    reset_circuit_breaker,
    with_circuit_breaker,
)


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == State.CLOSED

    def test_successful_call_stays_closed(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.call(lambda: 42)
        assert cb.state == State.CLOSED

    def test_failure_opens_circuit(self):
        def fail():
            raise Exception("fail")

        cb = CircuitBreaker("test", failure_threshold=2)
        try:
            cb.call(fail)
        except Exception:
            pass
        assert cb.state == State.CLOSED  # first failure
        try:
            cb.call(fail)
        except Exception:
            pass
        assert cb.state == State.OPEN

    def test_open_circuit_raises(self):
        def fail():
            raise Exception("fail")

        cb = CircuitBreaker("test", failure_threshold=1)
        try:
            cb.call(fail)
        except Exception:
            pass
        assert cb.state == State.OPEN
        try:
            cb.call(lambda: 42)
        except Exception as e:
            assert "Circuit breaker open" in str(e)

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        cb.reset()
        assert cb.state == State.CLOSED


class TestCircuitBreakerDecorator:
    def test_get_circuit_breaker_singleton(self):
        cb1 = get_circuit_breaker("svc1")
        cb2 = get_circuit_breaker("svc1")
        assert cb1 is cb2

    def test_get_circuit_breaker_states(self):
        get_circuit_breaker("svc_state")
        states = get_circuit_breaker_states()
        assert "svc_state" in states
        assert states["svc_state"] == "closed"

    def test_reset_circuit_breaker(self):
        cb = get_circuit_breaker("svc_reset", failure_threshold=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        assert cb.state == State.OPEN
        reset_circuit_breaker("svc_reset")
        assert cb.state == State.CLOSED

    def test_decorator_wraps_function(self):
        @with_circuit_breaker("decorated_svc", failure_threshold=2)
        def my_func():
            return "ok"

        assert my_func() == "ok"

    def test_decorator_opens_on_failure(self):
        call_count = 0

        @with_circuit_breaker("fail_svc", failure_threshold=2)
        def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        try:
            fail_func()
        except Exception:
            pass
        try:
            fail_func()
        except Exception:
            pass
        try:
            fail_func()
        except Exception:
            pass
        assert call_count == 2
        # Circuit now open, decorator should re-raise quickly
        try:
            fail_func()
        except Exception as e:
            assert "Circuit breaker open" in str(e)
        # Should not have called the function again
        assert call_count == 2
