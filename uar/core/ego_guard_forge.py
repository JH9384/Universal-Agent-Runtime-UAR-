"""Ego Guard Forge Integration Layer for UAR.

This module provides integration with the UOR Foundation's
ego-guard-forge security component.

The ego-guard-forge appears to be a security/guard-related
component for the UOR system, likely providing:
- Security policy enforcement
- Guardrail validation
- Access control mechanisms
- Security audit trails

This integration layer provides Python-native implementations
and bridges to the UOR security framework.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .uor_integration import UORObject, ObjectMode

logger = logging.getLogger(__name__)


@dataclass
class SecurityPolicy:
    """Represents a security policy in the ego-guard-forge."""

    policy_id: str
    name: str
    description: str
    rules: Dict[str, Any]
    enabled: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the policy against a given context."""
        # Placeholder for policy evaluation logic
        if not self.enabled:
            return True

        # Basic rule evaluation
        for rule_name, rule_value in self.rules.items():
            if rule_name in context:
                if context[rule_name] != rule_value:
                    return False

        return True

    def wrap_with_uor(self, source: str = "ego_guard") -> UORObject:
        """Wrap the security policy in a UOR object."""
        uor_obj = UORObject(
            data={
                "policy_id": self.policy_id,
                "name": self.name,
                "enabled": self.enabled,
                "rules": self.rules,
            },
            mode=ObjectMode.IMMUTABLE_SINGULAR,
        )
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "security_policy")
        uor_obj.add_schema_extension("security_policy", True)

        return uor_obj


class EgoGuardForgeIntegrator:
    """Main ego-guard-forge integration coordinator for UAR."""

    def __init__(self):
        self.enabled = True
        self.policies: Dict[str, SecurityPolicy] = {}
        self.audit_trail: List[Dict[str, Any]] = []

    def create_policy(
        self,
        policy_id: str,
        name: str,
        description: str,
        rules: Dict[str, Any],
    ) -> SecurityPolicy:
        """Create a security policy."""
        policy = SecurityPolicy(
            policy_id=policy_id,
            name=name,
            description=description,
            rules=rules,
        )
        self.policies[policy_id] = policy
        return policy

    def evaluate_policies(
        self, context: Dict[str, Any], policy_ids: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Evaluate security policies against context."""
        results = {}

        policies_to_check = (
            policy_ids if policy_ids else list(self.policies.keys())
        )

        for policy_id in policies_to_check:
            if policy_id in self.policies:
                policy = self.policies[policy_id]
                result = policy.evaluate(context)
                results[policy_id] = result

                # Audit trail
                self.audit_trail.append(
                    {
                        "policy_id": policy_id,
                        "result": result,
                        "timestamp": datetime.utcnow().isoformat(),
                        "context": context,
                    }
                )

        return results

    def integrate_with_uor(
        self, policy: SecurityPolicy, source: str = "ego_guard"
    ) -> UORObject:
        """Integrate security policy with UOR system."""
        uor_obj = policy.wrap_with_uor(source)

        # Add schema extensions for security tracking
        uor_obj.add_schema_extension("ego_guard_forge", True)
        uor_obj.add_schema_extension("policy_id", policy.policy_id)

        return uor_obj

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get security audit trail."""
        return self.audit_trail[-limit:]


# Global ego-guard-forge integrator instance
_ego_guard_integrator: Optional[EgoGuardForgeIntegrator] = None


def get_ego_guard_integrator() -> EgoGuardForgeIntegrator:
    """Get the global ego-guard-forge integrator instance."""
    global _ego_guard_integrator
    if _ego_guard_integrator is None:
        _ego_guard_integrator = EgoGuardForgeIntegrator()
    return _ego_guard_integrator


def reset_ego_guard_integrator():
    """Reset the global ego-guard-forge integrator (useful for testing)."""
    global _ego_guard_integrator
    _ego_guard_integrator = None


def create_security_policy(
    policy_id: str, name: str, description: str, rules: Dict[str, Any]
) -> SecurityPolicy:
    """Convenience function to create a security policy."""
    integrator = get_ego_guard_integrator()
    return integrator.create_policy(policy_id, name, description, rules)
