"""Performance regression benchmarks for UAR critical paths.

Run with: pytest tests/performance/test_benchmarks.py --benchmark-only
Compare: pytest tests/performance/test_benchmarks.py --benchmark-only \
    --benchmark-compare

Uses pytest-benchmark to track performance of hot paths over time.
"""

from unittest.mock import patch

import pytest

from uar.api.middleware import RateLimiter
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import GoalSpec, PipelineContext, RunRecord
from uar.memory.json_store import JsonRunStore
from uar.memory.sqlite_store import SqliteRunStore


class TestBenchmarkRateLimiter:
    """Benchmark the in-memory rate limiter under load."""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    def test_benchmark_is_allowed(self, benchmark, limiter):
        """Benchmark rate limit check (hot path on every request)."""
        benchmark(limiter.is_allowed, "test-key", 100, 60)

    def test_benchmark_get_remaining(self, benchmark, limiter):
        """Benchmark rate limit inspection (used by middleware)."""
        limiter.is_allowed("test-key", 100, 60)
        benchmark(limiter.get_remaining, "test-key", 100, 60)

    def test_benchmark_evict_empty(self, benchmark, limiter):
        """Benchmark cleanup of stale entries."""
        for i in range(1000):
            limiter.is_allowed(f"key-{i}", 1, 60)
        benchmark(limiter.evict_empty)


class TestBenchmarkCircuitBreaker:
    """Benchmark circuit breaker state transitions."""

    @pytest.fixture
    def cb(self):
        return CircuitBreaker(
            "bench", failure_threshold=3, recovery_timeout=1.0
        )

    def test_benchmark_successful_call(self, benchmark, cb):
        """Benchmark a successful call through the breaker."""
        benchmark(cb.call, lambda: "ok")

    def test_benchmark_open_state_rejection(self, benchmark, cb):
        """Benchmark rejection when circuit is OPEN."""
        # Force circuit OPEN
        def fail():
            raise ValueError("x")

        for _ in range(3):
            try:
                cb.call(fail)
            except Exception:
                pass
        assert cb.state.name == "OPEN"

        def _wrap():
            try:
                cb.call(lambda: "ok")
            except Exception:
                pass

        benchmark(_wrap)


class TestBenchmarkStores:
    """Benchmark store append and query operations."""

    @pytest.fixture
    def json_store(self, tmp_path):
        return JsonRunStore(path=str(tmp_path / "runs.jsonl"))

    @pytest.fixture
    def sqlite_store(self, tmp_path):
        return SqliteRunStore(path=str(tmp_path / "runs.db"))

    @pytest.fixture
    def sample_record(self):
        return RunRecord(
            run_id="bench-run",
            goal_id="g1",
            skills=["section_sum"],
            status="completed",
        )

    def test_benchmark_json_append(self, benchmark, json_store, sample_record):
        """Benchmark JsonRunStore.append (hot path)."""
        benchmark(json_store.append, sample_record)

    def test_benchmark_sqlite_append(
        self, benchmark, sqlite_store, sample_record
    ):
        """Benchmark SqliteRunStore.append (hot path)."""
        import itertools

        counter = itertools.count()

        def _append_unique():
            rec = RunRecord(
                run_id=f"bench-run-{next(counter)}",
                goal_id=sample_record.goal_id,
                skills=list(sample_record.skills),
                status=sample_record.status,
            )
            sqlite_store.append(rec)

        benchmark(_append_unique)

    def test_benchmark_json_get_by_run_id(
        self, benchmark, json_store, sample_record
    ):
        """Benchmark JsonRunStore.get_by_run_id."""
        json_store.append(sample_record)
        benchmark(json_store.get_by_run_id, "bench-run")

    def test_benchmark_sqlite_get_by_run_id(
        self, benchmark, sqlite_store, sample_record
    ):
        """Benchmark SqliteRunStore.get_by_run_id."""
        sqlite_store.append(sample_record)
        benchmark(sqlite_store.get_by_run_id, "bench-run")


class TestBenchmarkPipelineContext:
    """Benchmark PipelineContext event emission."""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(
            goal=GoalSpec(
                id="g1", user_intent="bench", objective="benchmark"
            ),
            _max_events=1000,
        )

    def test_benchmark_emit(self, benchmark, ctx):
        """Benchmark single event emission."""
        benchmark(ctx.emit, "test", {"k": "v"})

    def test_benchmark_emit_with_overflow(self, benchmark, tmp_path):
        """Benchmark emission with disk overflow enabled."""
        import os

        with patch.dict(os.environ, {"UAR_CONTEXT_DISK_OVERFLOW": "true"}):
            ctx = PipelineContext(
                goal=GoalSpec(
                    id="g1", user_intent="bench", objective="benchmark"
                ),
                _max_events=100,
            )
            benchmark(ctx.emit, "test", {"k": "v"})
