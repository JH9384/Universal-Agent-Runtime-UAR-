"""
Example: Using Network-AI guardrails and governance.

This example demonstrates how to use the guardrails and governance
integration for multi-agent systems, including budget tracking,
safety checks, and shared blackboard coordination.
"""

from uar.core.guardrails import (
    GovernanceSystem,
    GuardrailType,
    setup_default_guardrails,
)


def example_budget_management():
    """Manage agent budgets."""
    print("=== Budget Management ===")

    governance = GovernanceSystem()

    # Create budget for an agent
    budget = governance.create_budget(
        agent_id="research_agent",
        max_tokens=100000,
        max_api_calls=1000,
        max_cost_usd=10.0,
        max_duration_seconds=3600,
    )

    print(f"Agent: {budget.agent_id}")
    print(f"Max tokens: {budget.max_tokens}")
    print(f"Remaining tokens: {budget.remaining_tokens()}")
    print(f"Is exhausted: {budget.is_exhausted()}")

    # Track usage
    budget.used_tokens = 50000
    budget.used_api_calls = 500

    print("\nAfter usage:")
    print(f"Used tokens: {budget.used_tokens}")
    print(f"Remaining tokens: {budget.remaining_tokens()}")


def example_guardrail_checks():
    """Perform guardrail checks."""
    print("\n=== Guardrail Checks ===")

    governance = GovernanceSystem()
    setup_default_guardrails()

    # Check content safety
    violations = governance.guardrails.check(
        agent_id="test_agent",
        guardrail_type=GuardrailType.CONTENT_SAFETY,
        data="This is safe content",
    )

    print(f"Safe content violations: {len(violations)}")

    # Check unsafe content
    violations = governance.guardrails.check(
        agent_id="test_agent",
        guardrail_type=GuardrailType.CONTENT_SAFETY,
        data="This contains harmful content",
    )

    print(f"Unsafe content violations: {len(violations)}")
    for v in violations:
        print(f"  - {v.message}")


def example_blackboard():
    """Use shared blackboard for coordination."""
    print("\n=== Shared Blackboard ===")

    governance = GovernanceSystem()

    # Propose entries
    entry_id1 = governance.blackboard.propose(
        agent_id="agent1",
        key="research_result",
        value="AI research findings",
    )

    entry_id2 = governance.blackboard.propose(
        agent_id="agent2",
        key="analysis",
        value="Analysis of research",
    )

    print(f"Created entries: {entry_id1}, {entry_id2}")

    # Get value
    value = governance.blackboard.get("research_result")
    print(f"Retrieved value: {value}")

    # Get status
    status = governance.blackboard.get_status()
    print(f"Blackboard status: {status}")


def example_governance_status():
    """Get overall governance status."""
    print("\n=== Governance Status ===")

    governance = GovernanceSystem()
    setup_default_guardrails()

    # Create some budgets
    governance.create_budget(agent_id="agent1", max_tokens=50000)
    governance.create_budget(agent_id="agent2", max_tokens=100000)

    # Get status
    status = governance.get_system_status()
    print(f"Budget count: {status['budget_count']}")
    print(f"Policy count: {status['policy_count']}")
    print(f"Violation count: {len(status['violations'])}")


if __name__ == "__main__":
    example_budget_management()
    example_guardrail_checks()
    example_blackboard()
    example_governance_status()
