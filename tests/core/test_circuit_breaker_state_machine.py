"""Circuit breaker state-machine tests.

Pattern borrowed from danielfm/pybreaker.
Tests state transitions, failure thresholds, timeouts, and concurrency.
"""

from __future__ import annotations

import asyncio
import threading
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
        assert breaker.failures == 0

    def test_failure_increments_counter_while_closed(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=1)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "CLOSED"
        assert breaker.failures == 1

    def test_success_resets_failure_counter(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=1)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.failures == 1
        breaker.call(lambda: "ok")
        assert breaker.failures == 0

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
        assert breaker.failures == 0
        breaker.call(lambda: "ok")

    def test_reset_clears_last_failure_time(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        old_time = breaker.last_failure_time
        time.sleep(0.01)
        breaker.reset()
        assert breaker.last_failure_time != old_time


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
        assert breaker.failures == 100

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
        assert breaker.failures == 0


class TestCircuitBreakerHalfOpenRace:
    """Regression: half_open_max > 1 with concurrent calls."""

    def test_half_open_uses_success_counter_not_reservation_count(self):
        """Circuit must stay HALF_OPEN until half_open_max calls *succeed*,
        not just until half_open_max calls are *reserved*."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max=3,
        )
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        started = [threading.Event() for _ in range(3)]
        proceed = [threading.Event() for _ in range(3)]

        def make_call(idx):
            def fn():
                started[idx].set()
                proceed[idx].wait(timeout=2)
                return "ok"

            return breaker.call(fn)

        threads = [
            threading.Thread(target=make_call, args=(i,))
            for i in range(3)
        ]
        for t in threads:
            t.start()

        # Wait for all 3 calls to reserve their half-open slots
        for e in started:
            e.wait(timeout=2)
        time.sleep(0.05)

        # At this point all 3 have reserved: half_open_count == 3.
        # With the bug, the first success would close the circuit because
        # half_open_count (3) >= half_open_max (3).
        # With the fix, the circuit should stay HALF_OPEN until 3 successes.
        proceed[0].set()
        threads[0].join(timeout=2)
        assert breaker.state.name == "HALF_OPEN"

        proceed[1].set()
        threads[1].join(timeout=2)
        assert breaker.state.name == "HALF_OPEN"

        proceed[2].set()
        threads[2].join(timeout=2)
        assert breaker.state.name == "CLOSED"


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


class TestCircuitBreakerBaseException:
    """Regression: BaseException (CancelledError, KeyboardInterrupt)
    must not count as failures."""

    def test_keyboard_interrupt_not_counted_as_failure(self):
        breaker = CircuitBreaker("test", failure_threshold=1)

        def _raise_keyboard_interrupt():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            breaker.call(_raise_keyboard_interrupt)

        assert breaker.failures == 0
        assert breaker.state.name == "CLOSED"

    def test_system_exit_not_counted_as_failure(self):
        breaker = CircuitBreaker("test", failure_threshold=1)

        def _raise_system_exit():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            breaker.call(_raise_system_exit)

        assert breaker.failures == 0
        assert breaker.state.name == "CLOSED"

    def test_generator_exit_not_counted_as_failure(self):
        breaker = CircuitBreaker("test", failure_threshold=1)

        def _raise_generator_exit():
            raise GeneratorExit()

        with pytest.raises(GeneratorExit):
            breaker.call(_raise_generator_exit)

        assert breaker.failures == 0
        assert breaker.state.name == "CLOSED"

    def test_async_cancelled_error_not_counted_as_failure(self):
        breaker = CircuitBreaker("async_test", failure_threshold=1)

        async def _test():
            async def _slow():
                await asyncio.sleep(10)

            task = asyncio.create_task(breaker.call_async(_slow))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            assert breaker.failures == 0
            assert breaker.state.name == "CLOSED"

        import asyncio

        asyncio.run(_test())


class TestHalfOpenSlotDecrement:
    """Regression: half_open_count must be decremented when a call
    completes, otherwise the circuit stalls after half_open_max
    reservations even when earlier calls have finished."""

    def test_half_open_count_decremented_on_success_without_closure(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=3
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"
        assert breaker.half_open_count == 0

        breaker.call(lambda: "ok")
        assert breaker.state.name == "HALF_OPEN"
        assert breaker.half_open_count == 0
        assert breaker.half_open_successes == 1

    def test_half_open_count_decremented_on_failure_in_half_open(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=3
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"
        assert breaker.half_open_count == 0

        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"
        # half_open_count should not leak
        assert breaker.half_open_count == 0

    def test_subsequent_calls_allowed_after_partial_success(self):
        """With the bug, after half_open_max reservations none of which
        closed the circuit, all future calls would be rejected."""
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1, half_open_max=2
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        # First call succeeds but does not close (need 2 successes)
        breaker.call(lambda: "ok")
        assert breaker.state.name == "HALF_OPEN"
        assert breaker.half_open_successes == 1

        # Second call must be allowed through — with the bug it would be
        # rejected because half_open_count was never decremented.
        breaker.call(lambda: "ok")
        assert breaker.state.name == "CLOSED"


class TestTransitionResetsFailures:
    """Regression: failures must be cleared on OPEN → HALF_OPEN
    so that the health endpoint does not report stale failure counts."""

    def test_failures_reset_on_open_to_half_open_transition(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"
        assert breaker.failures == 1

        time.sleep(0.15)
        # Accessing .state triggers _transition()
        assert breaker.state.name == "HALF_OPEN"
        assert breaker.failures == 0


class TestHalfOpenSlotWithReset:
    """Regression: decrementing half_open_count must not go negative
    if reset() clears it while the call is in-flight."""

    def test_half_open_decrement_not_negative_after_reset(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"

        # Wait for automatic transition to half-open
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        started = threading.Event()
        proceed = threading.Event()

        def slow_call():
            started.set()
            proceed.wait(timeout=2)
            return "ok"

        call_thread = threading.Thread(target=lambda: breaker.call(slow_call))
        call_thread.start()
        started.wait(timeout=2)

        # Reset while in-flight — this zeros half_open_count
        breaker.reset()

        proceed.set()
        call_thread.join(timeout=2)
        assert breaker.state.name == "CLOSED"
        assert breaker.half_open_count >= 0


class TestGenerationInvalidationAfterReset:
    """Regression: in-flight failure after reset must not re-open circuit."""

    def test_failure_after_reset_does_not_reopen_sync(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1
        )
        # Open the circuit
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"

        # Wait for automatic transition to half-open
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        started = threading.Event()
        proceed = threading.Event()

        def slow_fail():
            started.set()
            proceed.wait(timeout=2)
            raise ValueError("post-reset failure")

        exc_holder = []

        def _target():
            try:
                breaker.call(slow_fail)
            except ValueError as e:
                exc_holder.append(e)

        call_thread = threading.Thread(target=_target)
        call_thread.start()
        started.wait(timeout=2)

        # Reset while the failing call is in-flight
        breaker.reset()
        assert breaker.state.name == "CLOSED"
        assert breaker.failures == 0

        proceed.set()
        call_thread.join(timeout=2)
        assert len(exc_holder) == 1
        # Circuit must stay closed — the stale failure was ignored
        assert breaker.state.name == "CLOSED"
        assert breaker.failures == 0

    @pytest.mark.asyncio
    async def test_failure_after_reset_does_not_reopen_async(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1
        )
        # Open the circuit
        with pytest.raises(ValueError):
            await breaker.call_async(_async_raise_error)
        assert breaker.state.name == "OPEN"

        # Wait for automatic transition to half-open
        await asyncio.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        started = asyncio.Event()
        proceed = asyncio.Event()

        async def slow_fail():
            started.set()
            await asyncio.wait_for(proceed.wait(), timeout=2)
            raise ValueError("post-reset failure")

        task = asyncio.create_task(breaker.call_async(slow_fail))
        await asyncio.wait_for(started.wait(), timeout=2)

        # Reset while the failing call is in-flight
        breaker.reset()
        assert breaker.state.name == "CLOSED"
        assert breaker.failures == 0

        proceed.set()
        with pytest.raises(ValueError):
            await asyncio.wait_for(task, timeout=2)
        # Circuit must stay closed — the stale failure was ignored
        assert breaker.state.name == "CLOSED"
        assert breaker.failures == 0

    def test_success_after_reset_does_not_affect_state_sync(self):
        breaker = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0.1
        )
        with pytest.raises(ValueError):
            breaker.call(_raise_error)
        assert breaker.state.name == "OPEN"

        # Wait for automatic transition to half-open
        time.sleep(0.15)
        assert breaker.state.name == "HALF_OPEN"

        started = threading.Event()
        proceed = threading.Event()

        def slow_call():
            started.set()
            proceed.wait(timeout=2)
            return "ok"

        call_thread = threading.Thread(target=lambda: breaker.call(slow_call))
        call_thread.start()
        started.wait(timeout=2)

        breaker.reset()
        proceed.set()
        call_thread.join(timeout=2)
        # Circuit should still be closed; stale success was ignored
        assert breaker.state.name == "CLOSED"
        assert breaker.half_open_count == 0


def _raise_error():
    raise ValueError("boom")


async def _async_raise_error():
    raise ValueError("async boom")
