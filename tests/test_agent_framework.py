"""
Tests for Microsoft Agent Framework integration.
"""

import pytest
from uar.core.agent_framework import (
    Agent,
    AgentMessage,
    MessageType,
    AgentOrchestrator,
    get_orchestrator,
    execute_agent_workflow,
)


def test_agent_message_creation():
    """Test creating an agent message."""
    message = AgentMessage(
        type=MessageType.TEXT,
        content="Test message",
        sender_id="agent1",
        recipient_id="agent2",
    )
    assert message.type == MessageType.TEXT
    assert message.content == "Test message"
    assert message.sender_id == "agent1"
    assert message.recipient_id == "agent2"
    assert message.id is not None


def test_agent_message_serialization():
    """Test agent message serialization."""
    message = AgentMessage(
        type=MessageType.TEXT,
        content="Test message",
    )
    data = message.to_dict()
    assert "id" in data
    assert data["type"] == "text"
    assert data["content"] == "Test message"


def test_agent_creation():
    """Test creating an agent."""
    agent = Agent(
        agent_id="test_agent",
        name="Test Agent",
        description="A test agent",
    )
    assert agent.agent_id == "test_agent"
    assert agent.name == "Test Agent"
    assert agent.description == "A test agent"
    assert agent.active is True


def test_agent_message_handler():
    """Test registering and using message handlers."""
    agent = Agent(
        agent_id="test_agent",
        name="Test Agent",
    )
    
    handler_called = []
    
    def handler(message: AgentMessage) -> AgentMessage:
        handler_called.append(message)
        return AgentMessage(
            type=MessageType.TEXT,
            content="Response",
            sender_id=agent.agent_id,
            reply_to=message.id,
        )
    
    agent.register_handler(MessageType.TEXT, handler)
    
    message = AgentMessage(
        type=MessageType.TEXT,
        content="Test",
    )
    
    response = agent.receive_message(message)
    
    assert len(handler_called) == 1
    assert response.content == "Response"
    assert response.reply_to == message.id


def test_orchestrator_registration():
    """Test registering agents with orchestrator."""
    orchestrator = AgentOrchestrator()
    agent = Agent(
        agent_id="test_agent",
        name="Test Agent",
    )
    
    orchestrator.register_agent(agent)
    
    assert orchestrator.get_agent("test_agent") == agent


def test_orchestrator_workflow():
    """Test orchestrator workflow management."""
    orchestrator = AgentOrchestrator()
    
    orchestrator.start_workflow("test_workflow", ["agent1", "agent2"])
    
    status = orchestrator.get_workflow_status("test_workflow")
    
    assert status["status"] == "active"
    assert status["agent_count"] == 2
    
    orchestrator.end_workflow("test_workflow")


def test_get_orchestrator_singleton():
    """Test global orchestrator singleton."""
    orchestrator1 = get_orchestrator()
    orchestrator2 = get_orchestrator()
    
    assert orchestrator1 is orchestrator2


def test_execute_agent_workflow():
    """Test executing an agent workflow."""
    orchestrator = get_orchestrator()
    
    # Register test agents
    agent1 = Agent(agent_id="agent1", name="Agent 1")
    agent2 = Agent(agent_id="agent2", name="Agent 2")
    
    orchestrator.register_agent(agent1)
    orchestrator.register_agent(agent2)
    
    # Execute workflow
    result = execute_agent_workflow(
        workflow_id="test_workflow",
        agent_sequence=["agent1", "agent2"],
        initial_message="Start workflow",
    )
    
    assert result["workflow_id"] == "test_workflow"
    assert result["status"] == "completed"
    assert len(result["results"]) == 2
