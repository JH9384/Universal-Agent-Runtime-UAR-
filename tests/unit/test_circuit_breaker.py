"""Unit tests for circuit breaker module"""

import pytest
import time
import threading

from uar.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    State,
)


class TestCircuitBreakerBasic:
    """Test basic circuit breaker functionality"""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state"""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30.0)
        assert cb.state == State.CLOSED

    def test_failure_threshold_opens_circuit(self):
        """Circuit opens after failure threshold is reached"""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30.0)

        def failing_function():
            raise Exception("Test failure")

        # First failure - circuit stays closed
        try:
            cb.call(failing_function)
        except Exception:
            pass
        assert cb.state == State.CLOSED

        # Second failure - circuit opens
        try:
            cb.call(failing_function)
        except Exception:
            pass
        assert cb.state == State.OPEN

    def test_circuit_prevents_calls_when_open(self):
        """Circuit raises error when trying to call while OPEN"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=30.0)

        def failing_function():
            raise Exception("Test failure")

        # Trigger circuit to open
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN

        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(failing_function)

    def test_success_resets_failure_count(self):
        """Successful calls reset failure count"""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30.0)

        def failing_function():
            raise Exception("Test failure")

        def successful_function():
            return "success"

        # Two failures
        try:
            cb.call(failing_function)
        except Exception:
            pass
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb._failures == 2

        # Success resets failures
        result = cb.call(successful_function)
        assert result == "success"
        assert cb._failures == 0

    def test_half_open_transition_after_timeout(self):
        """Circuit transitions to HALF_OPEN after recovery timeout"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # State should transition to HALF_OPEN
        assert cb.state == State.HALF_OPEN

    def test_half_open_failure_reopens_circuit(self):
        """Failure in HALF_OPEN state reopens circuit"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

        # Failure in HALF_OPEN should reopen circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN

    def test_half_open_success_closes_circuit(self):
        """Success in HALF_OPEN state closes circuit"""
        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max=1,
        )

        def failing_function():
            raise Exception("Test failure")

        def successful_function():
            return "success"

        # Open the circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass
        try:
            cb.call(failing_function)
        except Exception:
            pass

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

        # Success in HALF_OPEN should close circuit
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.state == State.CLOSED

    def test_reset_clears_all_state(self):
        """Reset clears circuit breaker state"""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=30.0)

        def failing_function():
            raise Exception("Test failure")

        # Open the circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN
        assert cb._failures == 2

        # Reset
        cb.reset()

        assert cb.state == State.CLOSED
        assert cb._failures == 0
        assert cb._half_open_count == 0


class TestCircuitBreakerConcurrency:
    """Test circuit breaker thread safety"""

    def test_concurrent_failures_opens_circuit(self):
        """Concurrent failures should correctly open circuit"""
        cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=30.0)

        def failing_function():
            raise Exception("Test failure")

        results = []
        errors = []

        def make_call():
            try:
                cb.call(failing_function)
                results.append("success")
            except Exception as e:
                errors.append(str(e))

        # Make 10 concurrent calls
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_call)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Circuit should be open
        assert cb.state == State.OPEN
        assert cb._failures >= 5

    def test_concurrent_successes_dont_corrupt_state(self):
        """Concurrent successes should not corrupt state"""
        cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=30.0)

        def successful_function():
            return "success"

        results = []

        def make_call():
            result = cb.call(successful_function)
            results.append(result)

        # Make 20 concurrent successful calls
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=make_call)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert len(results) == 20
        assert all(r == "success" for r in results)
        # Failure count should be 0
        assert cb._failures == 0
        assert cb.state == State.CLOSED


class TestCircuitBreakerParameters:
    """Test circuit breaker configuration parameters"""

    def test_custom_failure_threshold(self):
        """Custom failure threshold works correctly"""
        cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=30.0)
        assert cb.failure_threshold == 5

        def failing_function():
            raise Exception("Test failure")

        # 4 failures should not open circuit
        for _ in range(4):
            try:
                cb.call(failing_function)
            except Exception:
                pass

        assert cb.state == State.CLOSED

        # 5th failure opens circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN

    def test_custom_recovery_timeout(self):
        """Custom recovery timeout works correctly"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        assert cb.recovery_timeout == 0.05

        def failing_function():
            raise Exception("Test failure")

        # Open circuit
        try:
            cb.call(failing_function)
        except Exception:
            pass

        assert cb.state == State.OPEN

        # Wait less than timeout - should still be OPEN
        time.sleep(0.03)
        assert cb.state == State.OPEN

        # Wait longer than timeout - should transition to HALF_OPEN
        time.sleep(0.03)
        assert cb.state == State.HALF_OPEN

    def test_custom_half_open_max(self):
        """Custom half_open_max works correctly"""
        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max=2,
        )
        assert cb.half_open_max == 2

        def successful_function():
            return "success"

        # Open circuit
        def failing_function():
            raise Exception("Test failure")

        try:
            cb.call(failing_function)
        except Exception:
            pass

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

        # First success in HALF_OPEN - should stay HALF_OPEN (max=2)
        cb.call(successful_function)
        assert cb.state == State.HALF_OPEN
        assert cb._half_open_count == 1

        # Second success - should close circuit
        cb.call(successful_function)
        assert cb.state == State.CLOSED


class TestCircuitBreakerAdvanced:
    """Advanced state machine edge cases."""

    def test_half_open_max_blocks_extra_calls(self):
        """When half_open_count >= half_open_max, new calls are rejected."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max=1,
        )

        def failing():
            raise Exception("fail")

        def slow():
            time.sleep(0.5)
            return "ok"

        # Open circuit
        try:
            cb.call(failing)
        except Exception:
            pass

        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

        # Reserve the single half-open slot with a slow call
        # (execute outside lock so another call can try to get in)
        t = threading.Thread(target=lambda: cb.call(slow))
        t.start()
        time.sleep(0.05)  # Let slow call reserve slot

        # Extra call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "x")

        t.join()
        assert cb.state == State.CLOSED

    def test_pending_calls_tracked(self):
        """_pending_calls increments and decrements correctly."""
        cb = CircuitBreaker("test", failure_threshold=3)

        def fn():
            return "ok"

        assert cb._pending_calls == 0
        cb.call(fn)
        assert cb._pending_calls == 0

    def test_pending_calls_on_failure(self):
        """_pending_calls decrements even on failure."""
        cb = CircuitBreaker("test", failure_threshold=3)

        def fn():
            raise Exception("fail")

        assert cb._pending_calls == 0
        try:
            cb.call(fn)
        except Exception:
            pass
        assert cb._pending_calls == 0

    def test_mixed_concurrent_half_open(self):
        """Concurrent success and failure in half-open race safely."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max=3,
        )

        def fail():
            raise Exception("fail")

        # Open circuit
        for _ in range(2):
            try:
                cb.call(fail)
            except Exception:
                pass

        time.sleep(0.15)
        assert cb.state == State.HALF_OPEN

        results = []

        def make_call(success):
            def fn():
                if not success:
                    raise Exception("fail")
                return "ok"

            try:
                results.append(("success", cb.call(fn)))
            except CircuitBreakerOpenError:
                results.append(("cb_open", None))
            except Exception:
                results.append(("error", None))

        threads = [
            threading.Thread(target=make_call, args=(True,)),
            threading.Thread(target=make_call, args=(False,)),
            threading.Thread(target=make_call, args=(True,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Circuit should be deterministically closed or open
        assert cb.state in (State.CLOSED, State.OPEN)
        # At least one call got through
        assert len(results) == 3


class TestCircuitBreakerError:
    """Test CircuitBreakerOpenError"""

    def test_error_message(self):
        """Error message includes service name"""
        error = CircuitBreakerOpenError("test-service")
        assert "test-service" in str(error)
        assert "Circuit breaker open" in str(error)

    def test_error_code(self):
        """Error has correct error code"""
        from uar.core.exceptions import ErrorCode

        error = CircuitBreakerOpenError("test-service")
        assert error.code == ErrorCode.EXTERNAL_DOWN
