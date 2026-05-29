"""MonotonicDeadline tests with injectable fake clock.

Pattern borrowed from jd/tenacity (make_retry_state) and
PyrateLimiter (MonotonicClock injection).
"""

from __future__ import annotations

import time

import pytest

from uar.core.safe_utils import MonotonicDeadline, monotonic_timeout


class FakeClock:
    """Deterministic clock for timeout testing."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestMonotonicDeadlineWithFakeClock:
    """Deadline arithmetic without real sleeps."""

    def test_not_expired_when_within_timeout(self):
        d = MonotonicDeadline(60.0)
        assert not d.expired
        assert d.remaining > 59.0

    def test_expired_when_past_deadline(self):
        d = MonotonicDeadline(0.001)
        time.sleep(0.01)
        assert d.expired

    def test_remaining_time_decreases(self):
        d = MonotonicDeadline(10.0)
        assert d.remaining > 9.0
        time.sleep(0.01)
        assert d.remaining < 10.0


class TestMonotonicTimeoutWithFakeClock:
    """Context manager timeout with fake clock."""

    def test_no_error_when_block_completes_quickly(self):
        with monotonic_timeout(10.0, label="test_op"):
            pass

    def test_raises_timeout_when_block_too_slow(self):
        with pytest.raises(TimeoutError, match="test_op exceeded"):
            with monotonic_timeout(0.001, label="test_op"):
                time.sleep(0.02)

    def test_preserves_original_exception_when_not_expired(self):
        with pytest.raises(ValueError, match="inner error"):
            with monotonic_timeout(10.0):
                raise ValueError("inner error")

    def test_raises_timeout_when_block_raises_and_expired(self):
        with pytest.raises(TimeoutError, match="test_op exceeded"):
            with monotonic_timeout(0.001, label="test_op"):
                time.sleep(0.02)
                raise ValueError("inner error")
