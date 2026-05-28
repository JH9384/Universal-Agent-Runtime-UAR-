"""
Tests for guardrails and governance integration.
"""

from uar.core.guardrails import (
    GuardrailType,
    ViolationSeverity,
    GuardrailViolation,
    Budget,
    BlackboardEntry,
    SharedBlackboard,
    GuardrailChecker,
    GovernanceSystem,
    get_governance_system,
    setup_default_guardrails,
)


def test_guardrail_violation_creation():
    """Test creating a guardrail violation."""
    violation = GuardrailViolation(
        violation_id="test_violation",
        guardrail_type=GuardrailType.CONTENT_SAFETY,
        severity=ViolationSeverity.WARNING,
        message="Test violation message",
        agent_id="test_agent",
    )

    assert violation.violation_id == "test_violation"
    assert violation.guardrail_type == GuardrailType.CONTENT_SAFETY
    assert violation.severity == ViolationSeverity.WARNING


def test_budget_creation():
    """Test creating a budget."""
    budget = Budget(
        agent_id="test_agent",
        max_tokens=1000,
        max_api_calls=100,
        max_cost_usd=1.0,
    )

    assert budget.agent_id == "test_agent"
    assert budget.max_tokens == 1000
    assert budget.used_tokens == 0
    assert budget.is_exhausted() is False


def test_budget_tracking():
    """Test budget tracking."""
    budget = Budget(
        agent_id="test_agent",
        max_tokens=1000,
        max_api_calls=100,
    )

    budget.used_tokens = 500
    budget.used_api_calls = 50

    assert budget.remaining_tokens() == 500
    assert budget.remaining_api_calls() == 50
    assert budget.is_exhausted() is False

    budget.used_tokens = 1001
    assert budget.is_exhausted() is True


def test_blackboard_entry_creation():
    """Test creating a blackboard entry."""
    entry = BlackboardEntry(
        entry_id="test_entry",
        key="test_key",
        value="test_value",
        agent_id="test_agent",
    )

    assert entry.entry_id == "test_entry"
    assert entry.key == "test_key"
    assert entry.value == "test_value"
    assert entry.is_locked() is False


def test_blackboard_locking():
    """Test blackboard entry locking."""
    entry = BlackboardEntry(
        entry_id="test_entry",
        key="test_key",
        value="test_value",
        agent_id="agent1",
    )

    assert entry.acquire_lock("agent1", ttl_seconds=60) is True
    assert entry.is_locked() is True
    assert entry.locked_by == "agent1"

    assert entry.acquire_lock("agent2", ttl_seconds=60) is False

    entry.release_lock("agent1")
    assert entry.is_locked() is False


def test_shared_blackboard():
    """Test shared blackboard operations."""
    blackboard = SharedBlackboard()

    entry_id = blackboard.propose(
        agent_id="test_agent",
        key="test_key",
        value="test_value",
    )

    assert entry_id is not None

    value = blackboard.get("test_key")
    assert value == "test_value"

    status = blackboard.get_status()
    assert status["entry_count"] == 1


def test_guardrail_checker():
    """Test guardrail checker."""
    checker = GuardrailChecker()

    def test_checker(content):
        if "unsafe" in content.lower():
            return GuardrailViolation(
                violation_id="test",
                guardrail_type=GuardrailType.CONTENT_SAFETY,
                severity=ViolationSeverity.WARNING,
                message="Unsafe content detected",
            )
        return None

    checker.register_checker(GuardrailType.CONTENT_SAFETY, test_checker)

    violations = checker.check(
        agent_id="test_agent",
        guardrail_type=GuardrailType.CONTENT_SAFETY,
        data="This is unsafe content",
    )

    assert len(violations) == 1
    assert violations[0].message == "Unsafe content detected"


def test_governance_system_budget():
    """Test governance system budget management."""
    governance = GovernanceSystem()

    budget = governance.create_budget(
        agent_id="test_agent",
        max_tokens=1000,
    )

    assert budget.agent_id == "test_agent"

    retrieved = governance.get_budget("test_agent")
    assert retrieved == budget


def test_governance_system_budget_check():
    """Test governance system budget checking."""
    governance = GovernanceSystem()

    governance.create_budget(
        agent_id="test_agent",
        max_tokens=1000,
        max_api_calls=100,
    )

    # Check if individual requests are within budget
    # Test state persistence across calls
    assert governance.check_budget("test_agent", tokens=500) is True
    assert governance.check_budget("test_agent", tokens=500) is True
    # This should fail because we've now used 1000 tokens total
    assert governance.check_budget("test_agent", tokens=1) is False


def test_governance_system_policy():
    """Test governance system policy management."""
    governance = GovernanceSystem()

    def test_policy(context):
        return context.get("allowed", True)

    governance.register_policy("test_policy", test_policy)

    assert governance.check_policy("test_policy", {"allowed": True}) is True
    assert governance.check_policy("test_policy", {"allowed": False}) is False


def test_governance_system_status():
    """Test governance system status."""
    governance = GovernanceSystem()

    governance.create_budget(agent_id="test_agent", max_tokens=1000)

    status = governance.get_system_status()

    assert "blackboard" in status
    assert "budgets" in status
    assert "violations" in status
    assert "policies" in status
    assert status["budget_count"] == 1


def test_get_governance_system_singleton():
    """Test global governance system singleton."""
    governance1 = get_governance_system()
    governance2 = get_governance_system()

    assert governance1 is governance2


def test_setup_default_guardrails():
    """Test setup of default guardrails."""
    governance = get_governance_system()
    setup_default_guardrails()

    violations = governance.guardrails.check(
        agent_id="test_agent",
        guardrail_type=GuardrailType.CONTENT_SAFETY,
        data="This contains harmful content",
    )

    assert len(violations) > 0


class TestBudgetRemainingMethods:
    """Budget helper methods not covered by existing tests."""

    def test_remaining_cost(self):
        budget = Budget(agent_id="a", max_cost_usd=10.0, used_cost_usd=3.5)
        assert budget.remaining_cost() == 6.5

    def test_remaining_time(self):
        budget = Budget(agent_id="a", max_duration_seconds=100)
        assert budget.remaining_time() <= 100.0
        assert budget.remaining_time() >= 99.0

    def test_to_dict(self):
        budget = Budget(
            agent_id="a",
            max_tokens=100,
            used_tokens=50,
        )
        d = budget.to_dict()
        assert d["agent_id"] == "a"
        assert d["remaining_tokens"] == 50
        assert d["is_exhausted"] is False


class TestBlackboardEntryHelpers:
    """BlackboardEntry uncovered paths."""

    def test_to_dict(self):
        entry = BlackboardEntry(
            entry_id="e1", key="k", value="v", agent_id="a"
        )
        d = entry.to_dict()
        assert d["entry_id"] == "e1"
        assert d["is_locked"] is False
        assert d["lock_expiry"] is None

    def test_lock_expiry(self):
        entry = BlackboardEntry(
            entry_id="e1", key="k", value="v", agent_id="a"
        )
        import time

        entry.acquire_lock("a", ttl_seconds=1)
        assert entry.is_locked() is True
        time.sleep(1.1)
        assert entry.is_locked() is False


class TestSharedBlackboardAdvanced:
    """SharedBlackboard validate, commit, get with locked entries."""

    def test_validate_and_commit(self):
        bb = SharedBlackboard()
        eid = bb.propose("a", "k", "v")
        assert bb.validate(eid, lambda v: v == "v") is True
        assert bb.commit(eid, "a") is True

    def test_validate_missing_entry(self):
        bb = SharedBlackboard()
        assert bb.validate("missing", lambda v: True) is False

    def test_commit_wrong_agent(self):
        bb = SharedBlackboard()
        eid = bb.propose("a", "k", "v")
        assert bb.commit(eid, "b") is False

    def test_get_skips_locked(self):
        bb = SharedBlackboard()
        eid = bb.propose("a", "k", "v")
        bb.acquire_lock(eid, "a", ttl_seconds=60)
        assert bb.get("k") is None

    def test_get_unlocked(self):
        bb = SharedBlackboard()
        bb.propose("a", "k", "v")
        assert bb.get("k") == "v"


class TestGuardrailCheckerAdvanced:
    """GuardrailChecker check_all, get_violations, clear_violations."""

    def test_check_all(self):
        checker = GuardrailChecker()

        def _checker(content):
            return GuardrailViolation(
                violation_id="v1",
                guardrail_type=GuardrailType.CONTENT_SAFETY,
                severity=ViolationSeverity.WARNING,
                message="bad",
            )

        checker.register_checker(GuardrailType.CONTENT_SAFETY, _checker)
        results = checker.check_all(
            "a",
            {GuardrailType.CONTENT_SAFETY: "data"},
        )
        assert GuardrailType.CONTENT_SAFETY in results

    def test_get_violations_filters(self):
        checker = GuardrailChecker()
        v1 = GuardrailViolation(
            "v1", GuardrailType.CONTENT_SAFETY,
            ViolationSeverity.WARNING, "msg", agent_id="a",
        )
        v2 = GuardrailViolation(
            "v2", GuardrailType.RATE_LIMIT,
            ViolationSeverity.ERROR, "msg", agent_id="b",
        )
        checker.violations = [v1, v2]

        assert len(checker.get_violations(agent_id="a")) == 1
        assert len(
            checker.get_violations(severity=ViolationSeverity.ERROR)
        ) == 1

    def test_clear_violations(self):
        checker = GuardrailChecker()
        checker.violations = [
            GuardrailViolation(
                "v1", GuardrailType.CONTENT_SAFETY,
                ViolationSeverity.WARNING, "msg",
            ),
        ]
        checker.clear_violations()
        assert len(checker.violations) == 0

    def test_clear_violations_before_timestamp(self):
        from datetime import datetime, timezone

        checker = GuardrailChecker()
        old_ts = datetime(2020, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)
        old = GuardrailViolation(
            "v1", GuardrailType.CONTENT_SAFETY,
            ViolationSeverity.WARNING, "msg", timestamp=old_ts,
        )
        new = GuardrailViolation(
            "v2", GuardrailType.CONTENT_SAFETY,
            ViolationSeverity.WARNING, "msg",
        )
        checker.violations = [old, new]
        before_ts = datetime(
            2025, 1, 1, tzinfo=timezone.utc
        ).replace(tzinfo=None)
        checker.clear_violations(before=before_ts)
        assert len(checker.violations) == 1


class TestGovernanceSystemAdvanced:
    """GovernanceSystem edge cases."""

    def test_check_budget_no_budget_means_unlimited(self):
        gov = GovernanceSystem()
        assert gov.check_budget("unknown_agent", tokens=999999) is True

    def test_check_policy_not_found_means_allowed(self):
        gov = GovernanceSystem()
        assert gov.check_policy("missing", {}) is True

    def test_check_policy_exception_returns_false(self):
        gov = GovernanceSystem()
        gov.register_policy("bad", lambda ctx: 1 / 0)
        assert gov.check_policy("bad", {}) is False
