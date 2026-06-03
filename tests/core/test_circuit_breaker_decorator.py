"""Tests for uar.core.circuit_breaker_decorator.

Covers the decorator layer that wraps functions with circuit breaker
protection and exposes global state queries.
"""

import asyncio

import pytest

from uar.core.circuit_breaker import CircuitBreakerOpenError
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

    def test_reuse_warns_on_parameter_mismatch(self, caplog):
        """Regression: different params for same name must log a warning."""
        cb1 = get_circuit_breaker("warn_svc", failure_threshold=5)
        with caplog.at_level("WARNING"):
            cb2 = get_circuit_breaker("warn_svc", failure_threshold=3)
        assert cb1 is cb2
        assert "already exists with different" in caplog.text
        assert "ignored" in caplog.text

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

        states = asyncio.run(get_circuit_breaker_states())
        assert states["reset_me"] == "open"

        # Reset and call again
        assert asyncio.run(reset_circuit_breaker("reset_me")) is True
        states = asyncio.run(get_circuit_breaker_states())
        assert states["reset_me"] == "closed"

        # After reset, circuit is closed so raw exception propagates again
        with pytest.raises(ValueError, match="x"):
            fail_once()

    def test_reset_unknown_returns_false(self):
        assert asyncio.run(reset_circuit_breaker("nonexistent")) is False


class TestGetCircuitBreakerStates:
    def test_returns_current_states(self):
        get_circuit_breaker("stateful")
        states = asyncio.run(get_circuit_breaker_states())
        assert "stateful" in states
        assert states["stateful"] == "closed"

    def test_empty_when_no_breakers(self):
        # This is global state; we can only assert it returns a dict
        states = asyncio.run(get_circuit_breaker_states())
        assert isinstance(states, dict)


class TestSkillCacheParamWarning:
    def test_skill_cache_warns_on_maxsize_mismatch(self, caplog):
        """Regression: different maxsize for global cache must warn."""
        from uar.core.skill_cache import get_skill_cache

        # Reset global cache so this test is idempotent
        import uar.core.skill_cache as _sc
        with _sc._global_cache_lock:
            _sc._global_skill_cache = None

        cache1 = get_skill_cache(maxsize=512)
        with caplog.at_level("WARNING"):
            cache2 = get_skill_cache(maxsize=2048)
        assert cache1 is cache2
        assert "already created with maxsize=" in caplog.text
        assert "ignored" in caplog.text

        # Cleanup
        with _sc._global_cache_lock:
            _sc._global_skill_cache = None


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
                    asyncio.run(get_circuit_breaker_states())
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
                asyncio.run(reset_circuit_breaker(f"reset_test_{i % 50}"))
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


class TestWithCircuitBreakerAsync:
    def test_async_successful_call(self):
        @with_circuit_breaker("async_good_svc")
        async def async_reliable():
            return "ok"

        assert asyncio.run(async_reliable()) == "ok"

    def test_async_failure_opens_circuit(self):
        call_count = [0]

        @with_circuit_breaker("async_bad_svc", failure_threshold=1)
        async def async_flaky():
            call_count[0] += 1
            raise ValueError("boom")

        # First call: circuit closed, raw exception propagates
        with pytest.raises(ValueError, match="boom"):
            asyncio.run(async_flaky())

        # Circuit is now open; second call fails fast with wrapped error
        with pytest.raises(SkillExecutionError, match="Circuit breaker open"):
            asyncio.run(async_flaky())

    def test_async_open_raises_skill_execution_error(self):
        @with_circuit_breaker("async_err_svc", failure_threshold=1)
        async def async_always_fail():
            raise RuntimeError("fail")

        # First call: circuit closed, raw exception propagates
        with pytest.raises(RuntimeError, match="fail"):
            asyncio.run(async_always_fail())

        # Second call: circuit open, wrapped as SkillExecutionError
        with pytest.raises(SkillExecutionError, match="Circuit breaker open"):
            asyncio.run(async_always_fail())

    def test_async_passes_through_args_and_kwargs(self):
        @with_circuit_breaker("async_echo_svc")
        async def async_echo(a, b, c=None):
            return (a, b, c)

        assert asyncio.run(async_echo(1, 2, c=3)) == (1, 2, 3)

    def test_async_and_sync_share_same_circuit_breaker(self):
        """Async and sync wrappers for the same service name share one CB."""
        @with_circuit_breaker("shared_svc", failure_threshold=1)
        def sync_fn():
            raise ValueError("sync fail")

        @with_circuit_breaker("shared_svc", failure_threshold=1)
        async def async_fn():
            raise ValueError("async fail")

        # Open circuit via sync call
        with pytest.raises(ValueError):
            sync_fn()

        # Async call should see the same open circuit
        with pytest.raises(SkillExecutionError, match="Circuit breaker open"):
            asyncio.run(async_fn())


class TestGeneratorRejection:
    def test_rejects_sync_generator(self):
        with pytest.raises(TypeError, match="cannot wrap generator function"):
            @with_circuit_breaker("gen_svc")
            def gen_fn():
                yield 1

    def test_rejects_async_generator(self):
        with pytest.raises(TypeError, match="cannot wrap generator function"):
            @with_circuit_breaker("async_gen_svc")
            async def async_gen_fn():
                yield 1

    def test_rejection_includes_function_name(self):
        with pytest.raises(TypeError, match="named_gen"):
            @with_circuit_breaker("named_gen_svc")
            def named_gen():
                yield 1


class TestExceptionChaining:
    def test_skill_execution_error_chains_from_circuit_breaker_open(self):
        @with_circuit_breaker("chain_svc", failure_threshold=1)
        def chain_fail():
            raise ValueError("boom")

        # Open the circuit
        with pytest.raises(ValueError):
            chain_fail()

        # Next call should raise SkillExecutionError with __cause__ set
        with pytest.raises(SkillExecutionError) as exc_info:
            chain_fail()

        assert isinstance(exc_info.value.__cause__, CircuitBreakerOpenError)
        assert "chain_svc" in str(exc_info.value.__cause__)

    def test_async_error_chains_from_circuit_breaker_open(self):
        @with_circuit_breaker("async_chain_svc", failure_threshold=1)
        async def async_chain_fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            asyncio.run(async_chain_fail())

        with pytest.raises(SkillExecutionError) as exc_info:
            asyncio.run(async_chain_fail())

        assert isinstance(exc_info.value.__cause__, CircuitBreakerOpenError)


class TestWrapperMetadata:
    def test_sync_wrapper_preserves_name(self):
        @with_circuit_breaker("meta_svc")
        def my_skill():
            return "ok"

        assert my_skill.__name__ == "my_skill"

    def test_async_wrapper_preserves_name(self):
        @with_circuit_breaker("async_meta_svc")
        async def my_async_skill():
            return "ok"

        assert my_async_skill.__name__ == "my_async_skill"


class TestGetCircuitBreakerDetails:
    def test_returns_snapshot_dict(self):
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker_details,
        )

        get_circuit_breaker("detail_svc")
        details = asyncio.run(get_circuit_breaker_details())
        assert "detail_svc" in details
        assert details["detail_svc"]["state"] == "closed"
        assert "failures" in details["detail_svc"]
        assert "half_open_count" in details["detail_svc"]
        assert "half_open_successes" in details["detail_svc"]
        assert "last_failure_time" in details["detail_svc"]

    def test_reflects_failures(self):
        from uar.core.circuit_breaker_decorator import (
            get_circuit_breaker_details,
        )

        cb = get_circuit_breaker("detail_fail_svc", failure_threshold=1)
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
        except ValueError:
            pass
        details = asyncio.run(get_circuit_breaker_details())
        assert details["detail_fail_svc"]["state"] == "open"
        assert details["detail_fail_svc"]["failures"] == 1
