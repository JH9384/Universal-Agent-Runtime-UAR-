"""
Network-AI guardrails and governance integration for UAR.

This module provides guardrails and governance for multi-agent systems,
inspired by Network-AI, including shared blackboard with locking,
guardrails and budgets, and safety mechanisms.

Key features:
- Shared blackboard with atomic propose → validate → commit
- Guardrails for agent behavior
- Budget and resource limits
- Safety checks and validation
- Governance policies
- Agent accountability
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading
import uuid

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return a naive UTC datetime (no tzinfo).

    Replaces deprecated ``datetime.utcnow()``.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GuardrailType(Enum):
    """Types of guardrails."""

    CONTENT_SAFETY = "content_safety"
    RATE_LIMIT = "rate_limit"
    BUDGET = "budget"
    PERMISSION = "permission"
    COMPLIANCE = "compliance"
    OUTPUT_VALIDATION = "output_validation"


class ViolationSeverity(Enum):
    """Severity levels for violations."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class GuardrailViolation:
    """Represents a guardrail violation."""

    violation_id: str
    guardrail_type: GuardrailType
    severity: ViolationSeverity
    message: str
    agent_id: Optional[str] = None
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "violation_id": self.violation_id,
            "guardrail_type": self.guardrail_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class Budget:
    """Budget tracking for agent resources."""

    agent_id: str
    max_tokens: int = 100000
    max_api_calls: int = 1000
    max_cost_usd: float = 10.0
    max_duration_seconds: int = 3600

    used_tokens: int = 0
    used_api_calls: int = 0
    used_cost_usd: float = 0.0
    start_time: datetime = field(default_factory=_utcnow)

    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return (
            self.used_tokens >= self.max_tokens
            or self.used_api_calls >= self.max_api_calls
            or self.used_cost_usd >= self.max_cost_usd
            or (_utcnow() - self.start_time).total_seconds()
            >= self.max_duration_seconds
        )

    def remaining_tokens(self) -> int:
        """Get remaining tokens."""
        return max(0, self.max_tokens - self.used_tokens)

    def remaining_api_calls(self) -> int:
        """Get remaining API calls."""
        return max(0, self.max_api_calls - self.used_api_calls)

    def remaining_cost(self) -> float:
        """Get remaining budget in USD."""
        return max(0.0, self.max_cost_usd - self.used_cost_usd)

    def remaining_time(self) -> float:
        """Get remaining time in seconds."""
        elapsed = (_utcnow() - self.start_time).total_seconds()
        return max(0.0, self.max_duration_seconds - elapsed)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "max_tokens": self.max_tokens,
            "max_api_calls": self.max_api_calls,
            "max_cost_usd": self.max_cost_usd,
            "max_duration_seconds": self.max_duration_seconds,
            "used_tokens": self.used_tokens,
            "used_api_calls": self.used_api_calls,
            "used_cost_usd": self.used_cost_usd,
            "start_time": self.start_time.isoformat(),
            "remaining_tokens": self.remaining_tokens(),
            "remaining_api_calls": self.remaining_api_calls(),
            "remaining_cost": self.remaining_cost(),
            "remaining_time": self.remaining_time(),
            "is_exhausted": self.is_exhausted(),
        }


@dataclass
class BlackboardEntry:
    """Entry in the shared blackboard."""

    entry_id: str
    key: str
    value: Any
    agent_id: str
    timestamp: datetime = field(default_factory=_utcnow)
    locked_by: Optional[str] = None
    lock_expiry: Optional[datetime] = None

    def is_locked(self) -> bool:
        """Check if entry is locked."""
        if not self.locked_by:
            return False
        if self.lock_expiry:
            return _utcnow() < self.lock_expiry
        return True

    def acquire_lock(self, agent_id: str, ttl_seconds: int = 60):
        """Acquire lock on entry."""
        if self.is_locked() and self.locked_by != agent_id:
            return False
        self.locked_by = agent_id
        self.lock_expiry = _utcnow() + timedelta(seconds=ttl_seconds)
        return True

    def release_lock(self, agent_id: str):
        """Release lock on entry."""
        if self.locked_by == agent_id:
            self.locked_by = None
            self.lock_expiry = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "key": self.key,
            "value": self.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "locked_by": self.locked_by,
            "lock_expiry": (
                self.lock_expiry.isoformat() if self.lock_expiry else None
            ),
            "is_locked": self.is_locked(),
        }


class SharedBlackboard:
    """Shared blackboard for agent coordination with locking."""

    def __init__(self):
        self.entries: Dict[str, BlackboardEntry] = {}
        self.lock = threading.Lock()

    def propose(
        self,
        agent_id: str,
        key: str,
        value: Any,
    ) -> str:
        """Propose a change to the blackboard."""
        with self.lock:
            entry_id = str(uuid.uuid4())
            entry = BlackboardEntry(
                entry_id=entry_id,
                key=key,
                value=value,
                agent_id=agent_id,
            )
            self.entries[entry_id] = entry
            logger.info(
                "Agent %s proposed entry %s", agent_id, entry_id
            )
            return entry_id

    def validate(
        self,
        entry_id: str,
        validator: Callable[[Any], bool],
    ) -> bool:
        """Validate a proposed entry."""
        with self.lock:
            entry = self.entries.get(entry_id)
            if not entry:
                return False
            try:
                is_valid = validator(entry.value)
                logger.info(
                    "Entry %s validation: %s", entry_id, is_valid
                )
                return is_valid
            except Exception:
                logger.exception(
                    "Validation failed for %s", entry_id
                )
                return False

    def commit(
        self,
        entry_id: str,
        agent_id: str,
    ) -> bool:
        """Commit a validated entry."""
        with self.lock:
            entry = self.entries.get(entry_id)
            if not entry:
                return False
            if entry.agent_id != agent_id:
                logger.warning(
                    "Agent %s cannot commit entry from %s",
                    agent_id,
                    entry.agent_id,
                )
                return False

            # Entry is already in the blackboard, mark as committed
            logger.info(
                "Agent %s committed entry %s", agent_id, entry_id
            )
            return True

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the blackboard."""
        with self.lock:
            for entry in self.entries.values():
                if entry.key == key and not entry.is_locked():
                    return entry.value
        return None

    def acquire_lock(
        self,
        entry_id: str,
        agent_id: str,
        ttl_seconds: int = 60,
    ) -> bool:
        """Acquire lock on an entry."""
        with self.lock:
            entry = self.entries.get(entry_id)
            if not entry:
                return False
            return entry.acquire_lock(agent_id, ttl_seconds)

    def release_lock(self, entry_id: str, agent_id: str):
        """Release lock on an entry."""
        with self.lock:
            entry = self.entries.get(entry_id)
            if entry:
                entry.release_lock(agent_id)

    def get_status(self) -> Dict[str, Any]:
        """Get blackboard status."""
        with self.lock:
            return {
                "entry_count": len(self.entries),
                "locked_entries": sum(
                    1 for e in self.entries.values() if e.is_locked()
                ),
                "entries": [e.to_dict() for e in self.entries.values()],
            }


class GuardrailChecker:
    """Checks for guardrail violations."""

    def __init__(self):
        self.checkers: Dict[GuardrailType, List[Callable]] = {}
        self.violations: List[GuardrailViolation] = []
        self.lock = threading.Lock()

    def register_checker(
        self,
        guardrail_type: GuardrailType,
        checker: Callable[[Any], Optional[GuardrailViolation]],
    ):
        """Register a guardrail checker."""
        if guardrail_type not in self.checkers:
            self.checkers[guardrail_type] = []
        self.checkers[guardrail_type].append(checker)

    def check(
        self,
        agent_id: str,
        guardrail_type: GuardrailType,
        data: Any,
    ) -> List[GuardrailViolation]:
        """Check for violations of a specific guardrail type."""
        violations = []
        checkers = self.checkers.get(guardrail_type, [])

        for checker in checkers:
            try:
                violation = checker(data)
                if violation:
                    violation.agent_id = agent_id
                    violations.append(violation)
            except Exception:
                logger.exception("Guardrail checker failed")

        with self.lock:
            self.violations.extend(violations)

        return violations

    def check_all(
        self,
        agent_id: str,
        data: Dict[GuardrailType, Any],
    ) -> Dict[GuardrailType, List[GuardrailViolation]]:
        """Check all guardrail types."""
        results = {}
        for guardrail_type, value in data.items():
            violations = self.check(agent_id, guardrail_type, value)
            if violations:
                results[guardrail_type] = violations
        return results

    def get_violations(
        self,
        agent_id: Optional[str] = None,
        severity: Optional[ViolationSeverity] = None,
    ) -> List[GuardrailViolation]:
        """Get violations with optional filters."""
        with self.lock:
            violations = self.violations
            if agent_id:
                violations = [v for v in violations if v.agent_id == agent_id]
            if severity:
                violations = [v for v in violations if v.severity == severity]
            return violations

    def clear_violations(self, before: Optional[datetime] = None):
        """Clear violations."""
        with self.lock:
            if before:
                self.violations = [
                    v for v in self.violations if v.timestamp > before
                ]
            else:
                self.violations.clear()


class GovernanceSystem:
    """Governance system for multi-agent coordination."""

    def __init__(self):
        self.blackboard = SharedBlackboard()
        self.guardrails = GuardrailChecker()
        self.budgets: Dict[str, Budget] = {}
        self.policies: Dict[str, Callable] = {}

    def create_budget(
        self,
        agent_id: str,
        max_tokens: int = 100000,
        max_api_calls: int = 1000,
        max_cost_usd: float = 10.0,
        max_duration_seconds: int = 3600,
    ) -> Budget:
        """Create a budget for an agent."""
        budget = Budget(
            agent_id=agent_id,
            max_tokens=max_tokens,
            max_api_calls=max_api_calls,
            max_cost_usd=max_cost_usd,
            max_duration_seconds=max_duration_seconds,
        )
        self.budgets[agent_id] = budget
        logger.info("Created budget for agent %s", agent_id)
        return budget

    def get_budget(self, agent_id: str) -> Optional[Budget]:
        """Get budget for an agent."""
        return self.budgets.get(agent_id)

    def check_budget(
        self,
        agent_id: str,
        tokens: int = 0,
        api_calls: int = 0,
        cost_usd: float = 0.0,
    ) -> bool:
        """Check if action is within budget."""
        budget = self.get_budget(agent_id)
        if not budget:
            return True  # No budget means unlimited

        # Check whether adding these resources would *exceed* the
        # budget before actually consuming them, so that exactly
        # reaching the limit is still allowed.
        would_exceed = (
            budget.used_tokens + tokens > budget.max_tokens
            or budget.used_api_calls + api_calls > budget.max_api_calls
            or budget.used_cost_usd + cost_usd > budget.max_cost_usd
        )
        if would_exceed:
            return False

        budget.used_tokens += tokens
        budget.used_api_calls += api_calls
        budget.used_cost_usd += cost_usd

        return True

    def register_policy(
        self,
        policy_name: str,
        policy: Callable[[Dict[str, Any]], bool],
    ):
        """Register a governance policy."""
        self.policies[policy_name] = policy
        logger.info("Registered policy: %s", policy_name)

    def check_policy(
        self,
        policy_name: str,
        context: Dict[str, Any],
    ) -> bool:
        """Check if a policy is satisfied."""
        policy = self.policies.get(policy_name)
        if not policy:
            return True  # No policy means allowed
        try:
            return policy(context)
        except Exception:
            logger.exception("Policy check failed for %s", policy_name)
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall governance system status."""
        return {
            "blackboard": self.blackboard.get_status(),
            "budgets": {
                agent_id: budget.to_dict()
                for agent_id, budget in self.budgets.items()
            },
            "violations": [
                v.to_dict() for v in self.guardrails.get_violations()
            ],
            "policies": list(self.policies.keys()),
            "budget_count": len(self.budgets),
            "policy_count": len(self.policies),
        }


# Global governance system instance
_governance_system: Optional[GovernanceSystem] = None


def get_governance_system() -> GovernanceSystem:
    """Get the global governance system instance."""
    global _governance_system
    if _governance_system is None:
        _governance_system = GovernanceSystem()
    return _governance_system


def setup_default_guardrails():
    """Setup default guardrails for common use cases."""
    governance = get_governance_system()

    # Content safety checker
    def content_safety_checker(content: str) -> Optional[GuardrailViolation]:
        """Check for unsafe content."""
        unsafe_keywords = ["harmful", "illegal", "violent"]
        content_lower = content.lower()

        for keyword in unsafe_keywords:
            if keyword in content_lower:
                return GuardrailViolation(
                    violation_id=str(uuid.uuid4()),
                    guardrail_type=GuardrailType.CONTENT_SAFETY,
                    severity=ViolationSeverity.WARNING,
                    message=f"Unsafe content detected: {keyword}",
                )
        return None

    governance.guardrails.register_checker(
        GuardrailType.CONTENT_SAFETY,
        content_safety_checker,
    )

    # Rate limit checker
    def rate_limit_checker(
        data: Dict[str, Any],
    ) -> Optional[GuardrailViolation]:
        """Check for rate limit violations."""
        requests_per_minute = data.get("requests_per_minute", 0)
        if requests_per_minute > 100:
            return GuardrailViolation(
                violation_id=str(uuid.uuid4()),
                guardrail_type=GuardrailType.RATE_LIMIT,
                severity=ViolationSeverity.ERROR,
                message=(
                    f"Rate limit exceeded: {requests_per_minute} requests/min"
                ),
            )
        return None

    governance.guardrails.register_checker(
        GuardrailType.RATE_LIMIT,
        rate_limit_checker,
    )

    logger.info("Default guardrails setup")
