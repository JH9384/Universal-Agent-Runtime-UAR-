"""
Example: Using Microsoft Agent Framework patterns.

This example demonstrates how to use the agent workflow integration
to execute multi-agent workflows with agent-to-agent communication.
"""

from uar.core.agent_framework import (
    Agent,
    AgentOrchestrator,
    AgentMessage,
    MessageType,
    execute_agent_workflow,
)


def example_basic_workflow():
    """Execute a basic multi-agent workflow."""
    print("=== Basic Agent Workflow ===")

    orchestrator = AgentOrchestrator()

    # Create agents
    agent1 = Agent(agent_id="researcher", name="Researcher")
    agent2 = Agent(agent_id="analyst", name="Analyst")

    orchestrator.register_agent(agent1)
    orchestrator.register_agent(agent2)

    # Execute workflow
    result = execute_agent_workflow(
        workflow_id="research_analysis",
        agent_sequence=["researcher", "analyst"],
        initial_message="Research AI frameworks and analyze their capabilities",  # noqa: E501
    )

    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Status: {result['status']}")
    print(f"Results: {result['results']}")


def example_agent_communication():
    """Demonstrate agent-to-agent communication."""
    print("\n=== Agent Communication ===")

    agent1 = Agent(agent_id="agent1", name="Agent 1")
    agent2 = Agent(agent_id="agent2", name="Agent 2")

    # Register message handler
    def handler(message: AgentMessage):
        return AgentMessage(
            type=MessageType.TEXT,
            content=f"Received: {message.content}",
            sender_id=agent1.agent_id,
            reply_to=message.id,
        )

    agent1.register_handler(MessageType.TEXT, handler)

    # Send message
    msg = AgentMessage(
        type=MessageType.TEXT,
        content="Hello from agent 2",
        sender_id=agent2.agent_id,
        recipient_id=agent1.agent_id,
    )

    response = agent1.receive_message(msg)
    print(f"Response: {response.content}")


if __name__ == "__main__":
    example_basic_workflow()
    example_agent_communication()
