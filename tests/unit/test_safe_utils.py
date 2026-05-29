"""Tests for uar.core.safe_utils guardrails."""

import logging
import time

import pytest

from uar.core.safe_utils import (
    MonotonicDeadline,
    TrackedLock,
    class_lru_cache,
    get_safe_logger,
    monotonic_timeout,
    safe_getattr,
    swallow,
)


class TestSwallow:
    def test_swallow_logs_and_returns_default(self, caplog):
        caplog.set_level(logging.WARNING)
        with swallow(return_value=42):
            raise ValueError("boom")
        assert "boom" in caplog.text

    def test_swallow_no_exception_no_log(self, caplog):
        caplog.set_level(logging.WARNING)
        with swallow(return_value=42):
            pass
        assert caplog.text == ""

    def test_swallow_custom_logger(self, caplog):
        custom = logging.getLogger("test_safe_utils_custom")
        custom.setLevel(logging.WARNING)
        with swallow(log=custom, msg="cache miss", return_value=0):
            raise RuntimeError("redis down")
        assert "cache miss" in caplog.text
        assert "redis down" in caplog.text

    def test_swallow_yields_return_value(self, caplog):
        caplog.set_level(logging.WARNING)
        with swallow(return_value=42) as val:
            raise ValueError("boom")
        assert val == 42
        assert "boom" in caplog.text

    def test_swallow_yields_none_when_no_exception(self):
        with swallow(return_value=99) as val:
            pass
        assert val == 99


class TestMonotonicDeadline:
    def test_not_expired_immediately(self):
        d = MonotonicDeadline(timeout=10.0)
        assert not d.expired
        assert d.remaining > 9.0

    def test_expires_after_timeout(self):
        d = MonotonicDeadline(timeout=0.01)
        time.sleep(0.02)
        assert d.expired
        assert d.remaining == 0.0

    def test_context_manager_raises_on_expiry(self):
        with pytest.raises(TimeoutError):
            with monotonic_timeout(0.001, label="test") as d:
                time.sleep(0.02)
                assert d.expired

    def test_context_manager_ok_when_fast(self):
        with monotonic_timeout(5.0) as d:
            assert not d.expired

    def test_context_manager_raises_timeout_when_block_raises_and_expired(
        self,
    ):
        with pytest.raises(TimeoutError, match="test_op exceeded"):
            with monotonic_timeout(0.001, label="test_op"):
                time.sleep(0.02)
                raise ValueError("inner error")

    def test_context_manager_preserves_original_exception_when_not_expired(
        self,
    ):
        with pytest.raises(ValueError, match="inner error"):
            with monotonic_timeout(5.0):
                raise ValueError("inner error")


class TestSafeGetattr:
    class Obj:
        run_id = "abc"

    def test_primary_hit(self):
        assert safe_getattr(self.Obj, "run_id") == "abc"

    def test_fallback_warns(self, caplog):
        caplog.set_level(logging.WARNING)
        val = safe_getattr(self.Obj, "missing", "run_id", default="x")
        assert val == "abc"
        assert "fallback used" in caplog.text

    def test_missing_raises(self):
        with pytest.raises(AttributeError):
            safe_getattr(self.Obj, "nope")

    def test_missing_returns_default(self):
        assert safe_getattr(self.Obj, "nope", default=42) == 42


class TestSafeLogger:
    def test_passes_parameterized_message(self, caplog):
        caplog.set_level(logging.INFO)
        log = get_safe_logger("test_safe")
        log.info("hello %s", "world")
        assert "hello world" in caplog.text

    def test_strict_mode_rejects_fstring(self, monkeypatch):
        monkeypatch.setenv("UAR_STRICT_LOGGING", "1")
        log = get_safe_logger("test_safe_strict")
        with pytest.raises(RuntimeError, match="f-string detected"):
            log.info("hello {world}")

    def test_strict_mode_allows_percent(self, monkeypatch, caplog):
        monkeypatch.setenv("UAR_STRICT_LOGGING", "1")
        caplog.set_level(logging.INFO)
        log = get_safe_logger("test_safe_pct")
        log.info("hello %s", "world")
        assert "hello world" in caplog.text


class TestTrackedLock:
    def test_acquire_and_release(self):
        lock = TrackedLock()
        assert lock.acquire()
        assert lock.held
        lock.release()
        assert not lock.held

    def test_context_manager(self):
        lock = TrackedLock()
        with lock:
            assert lock.held
        assert not lock.held

    def test_rlock(self):
        lock = TrackedLock(rlock=True)
        with lock:
            with lock:
                assert lock.held
            assert lock.held
        assert not lock.held

    def test_release_without_acquire(self):
        lock = TrackedLock()
        with pytest.raises(RuntimeError):
            lock.release()


class TestClassLruCache:
    def test_caches_across_instances(self):
        call_count = 0

        class Planner:
            @class_lru_cache(maxsize=4)
            def plan(self, goal_id: str, skills: tuple) -> str:
                nonlocal call_count
                call_count += 1
                return f"{goal_id}-{len(skills)}"

        p1 = Planner()
        p2 = Planner()

        assert p1.plan("g1", ("a", "b")) == "g1-2"
        assert p2.plan("g1", ("a", "b")) == "g1-2"
        assert call_count == 1  # shared cache

        assert p1.plan("g2", ("c",)) == "g2-1"
        assert call_count == 2

    def test_different_args_different_results(self):
        class Planner:
            @class_lru_cache(maxsize=4)
            def plan(self, goal_id: str, skills: tuple) -> str:
                return f"{goal_id}-{len(skills)}"

        p = Planner()
        assert p.plan("g1", ("a",)) == "g1-1"
        assert p.plan("g1", ("a", "b")) == "g1-2"
