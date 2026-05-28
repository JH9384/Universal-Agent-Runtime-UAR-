"""Property-based tests using Hypothesis.

Inspired by external frameworks (MAIA, PyBreaker, Hypothesis) for
fuzzing agent system behavior.
"""

import time

from hypothesis import given, settings, strategies as st
import pytest

from uar.core.circuit_breaker import (
    CircuitBreaker,
    State,
)
from uar.core.exceptions import ValidationError
from uar.core.validation import validate_goal, validate_timeout


class TestCircuitBreakerProperties:
    """Property-based circuit breaker state machine tests."""

    @given(
        st.integers(min_value=1, max_value=10),
        st.floats(min_value=0.01, max_value=1.0),
        st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_failure_threshold_opens_circuit(
        self, threshold, recovery, half_max
    ):
        """For any valid threshold, circuit opens after N failures."""
        cb = CircuitBreaker(
            "fuzz", failure_threshold=threshold,
            recovery_timeout=recovery, half_open_max=half_max,
        )

        def fail():
            raise ValueError("x")

        for _ in range(threshold):
            try:
                cb.call(fail)
            except ValueError:
                pass

        assert cb.state == State.OPEN

    @given(
        st.integers(min_value=1, max_value=10),
        st.floats(min_value=0.01, max_value=1.0),
    )
    @settings(max_examples=30, deadline=None)
    def test_success_after_failure_resets(self, threshold, recovery):
        """Success after any number of failures below threshold resets."""
        cb = CircuitBreaker(
            "fuzz", failure_threshold=threshold,
            recovery_timeout=recovery,
        )

        def fail():
            raise ValueError("x")

        def ok():
            return "ok"

        # Fail one less than threshold
        for _ in range(threshold - 1):
            try:
                cb.call(fail)
            except ValueError:
                pass

        assert cb.state == State.CLOSED
        assert cb._failures == threshold - 1

        # Success resets
        cb.call(ok)
        assert cb._failures == 0
        assert cb.state == State.CLOSED

    @given(
        st.integers(min_value=1, max_value=5),
        st.floats(min_value=0.01, max_value=0.5),
    )
    @settings(max_examples=30, deadline=None)
    def test_recovery_timeout_transitions_to_half_open(
        self, threshold, recovery
    ):
        """After recovery timeout, OPEN transitions to HALF_OPEN."""
        cb = CircuitBreaker(
            "fuzz", failure_threshold=threshold,
            recovery_timeout=recovery,
        )

        def fail():
            raise ValueError("x")

        for _ in range(threshold):
            try:
                cb.call(fail)
            except ValueError:
                pass

        assert cb.state == State.OPEN
        time.sleep(recovery + 0.05)
        assert cb.state == State.HALF_OPEN

    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=30, deadline=None)
    def test_never_exceeds_failure_counter(self, num_successes):
        """Only failures increment counter; successes reset it."""
        cb = CircuitBreaker("fuzz", failure_threshold=100)

        def ok():
            return "ok"

        for _ in range(num_successes):
            cb.call(ok)

        assert cb._failures == 0
        assert cb.state == State.CLOSED


class TestValidationProperties:
    """Property-based validation tests."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_validate_goal_never_crash(self, goal):
        """validate_goal handles any string input without crashing."""
        try:
            validate_goal(goal)
        except ValidationError:
            pass  # Rejecting invalid is correct

    @given(st.one_of(st.none(), st.floats(), st.integers(), st.text()))
    @settings(max_examples=50)
    def test_validate_timeout_never_crash(self, value):
        """validate_timeout handles any input type without crashing."""
        try:
            validate_timeout(value)
        except ValidationError:
            pass  # Rejecting invalid is correct

    @given(st.floats(min_value=0.1, max_value=300.0))
    @settings(max_examples=50)
    def test_validate_timeout_accepts_positive_floats(self, value):
        """Any positive float <= 300 should be accepted."""
        result = validate_timeout(value)
        assert result == pytest.approx(value)

    @given(st.integers(min_value=1, max_value=300))
    @settings(max_examples=50)
    def test_validate_timeout_accepts_positive_ints(self, value):
        """Any positive int <= 300 should be accepted."""
        result = validate_timeout(value)
        assert result == float(value)

    @given(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
    ))
    @settings(max_examples=50)
    def test_validate_goal_accepts_simple_alphanumeric(self, goal):
        """Simple alphanumeric goals without dangerous chars should pass."""
        if len(goal) >= 1 and len(goal) <= 500:
            try:
                validate_goal(goal)
            except ValidationError as exc:
                # Should not reject simple alphanumeric text
                assert "too long" not in str(exc).lower()
