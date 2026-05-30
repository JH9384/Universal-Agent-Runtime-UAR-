"""
Tests for Microsoft Agent Framework integration.
"""

import pytest
from uar.core.agent_framework import (
    Agent,
    AgentMessage,
    MessageType,
    AgentCapability,
    AgentOrchestrator,
    get_orchestrator,
    execute_agent_workflow,
    AutoGenAdapter,
    create_uar_agent,
    AUTOGEN_AVAILABLE,
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


@pytest.mark.asyncio
async def test_agent_message_handler():
    """Test registering and using message handlers."""
    agent = Agent(
        agent_id="test_agent",
        name="Test Agent",
    )

    handler_called = []

    async def handler(message: AgentMessage) -> AgentMessage:
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

    response = await agent.receive_message(message)

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


@pytest.mark.asyncio
async def test_execute_agent_workflow():
    """Test executing an agent workflow."""
    orchestrator = get_orchestrator()

    # Register test agents
    agent1 = Agent(agent_id="agent1", name="Agent 1")
    agent2 = Agent(agent_id="agent2", name="Agent 2")

    orchestrator.register_agent(agent1)
    orchestrator.register_agent(agent2)

    # Execute workflow
    result = await execute_agent_workflow(
        workflow_id="test_workflow",
        agent_sequence=["agent1", "agent2"],
        initial_message="Start workflow",
    )

    assert result["workflow_id"] == "test_workflow"
    assert result["status"] == "completed"
    assert len(result["results"]) == 2


# ---------------------------------------------------------------------------
# Coverage gap tests
# ---------------------------------------------------------------------------


def test_agent_message_from_dict():
    """AgentMessage.from_dict must reconstruct correctly."""
    msg = AgentMessage(
        type=MessageType.TOOL_CALL,
        content="hi",
        sender_id="a1",
        recipient_id="a2",
    )
    data = msg.to_dict()
    restored = AgentMessage.from_dict(data)
    assert restored.type == MessageType.TOOL_CALL
    assert restored.content == "hi"
    assert restored.sender_id == "a1"


@pytest.mark.asyncio
async def test_agent_send_message():
    """Agent.send_message must set sender/recipient and route."""
    a1 = Agent(agent_id="a1", name="A1")
    a2 = Agent(agent_id="a2", name="A2")

    async def handler(msg):
        return AgentMessage(type=MessageType.TEXT, content="ok")

    a2.register_handler(MessageType.TEXT, handler)

    msg = AgentMessage(type=MessageType.TEXT, content="hello")
    response = await a1.send_message(msg, a2)
    assert response.content == "ok"
    assert msg.sender_id == "a1"
    assert msg.recipient_id == "a2"


@pytest.mark.asyncio
async def test_agent_inactive_rejects_message():
    """Inactive agent must return an error message."""
    agent = Agent(agent_id="a1", name="A1")
    agent.active = False
    msg = AgentMessage(type=MessageType.TEXT, content="hi")
    response = await agent.receive_message(msg)
    assert response.type == MessageType.ERROR
    assert "not active" in response.content


@pytest.mark.asyncio
async def test_agent_sync_handler():
    """Synchronous handlers must work."""
    agent = Agent(agent_id="a1", name="A1")

    def sync_handler(msg):
        return AgentMessage(type=MessageType.TEXT, content="sync")

    agent.register_handler(MessageType.TEXT, sync_handler)
    msg = AgentMessage(type=MessageType.TEXT, content="hi")
    response = await agent.receive_message(msg)
    assert response.content == "sync"


@pytest.mark.asyncio
async def test_agent_handler_exception():
    """Handler exceptions must produce error message and stop iteration."""
    agent = Agent(agent_id="a1", name="A1")

    async def bad_handler(msg):
        raise RuntimeError("boom")

    async def second_handler(msg):
        return AgentMessage(type=MessageType.TEXT, content="second")

    agent.register_handler(MessageType.TEXT, bad_handler)
    agent.register_handler(MessageType.TEXT, second_handler)
    msg = AgentMessage(type=MessageType.TEXT, content="hi")
    response = await agent.receive_message(msg)
    assert response.type == MessageType.ERROR
    assert "Handler error" in response.content


def test_agent_get_capability_found():
    cap = AgentCapability(name="sum", description="add")
    agent = Agent(agent_id="a1", name="A1", capabilities=[cap])
    assert agent.get_capability("sum") == cap


def test_agent_get_capability_not_found():
    agent = Agent(agent_id="a1", name="A1")
    assert agent.get_capability("missing") is None


def test_orchestrator_unregister():
    orch = AgentOrchestrator()
    agent = Agent(agent_id="a1", name="A1")
    orch.register_agent(agent)
    orch.unregister_agent("a1")
    assert orch.get_agent("a1") is None
    # Idempotent
    orch.unregister_agent("a1")


@pytest.mark.asyncio
async def test_orchestrator_route_no_recipient():
    orch = AgentOrchestrator()
    msg = AgentMessage(type=MessageType.TEXT, content="hi")
    response = await orch.route_message(msg)
    assert response is None


@pytest.mark.asyncio
async def test_orchestrator_route_missing_agent():
    orch = AgentOrchestrator()
    msg = AgentMessage(
        type=MessageType.TEXT,
        content="hi",
        recipient_id="missing",
    )
    response = await orch.route_message(msg)
    assert response.type == MessageType.ERROR
    assert "not found" in response.content


def test_orchestrator_workflow_not_found():
    orch = AgentOrchestrator()
    status = orch.get_workflow_status("missing")
    assert status["status"] == "not_found"


def test_orchestrator_end_workflow_not_found():
    orch = AgentOrchestrator()
    orch.end_workflow("missing")  # must not raise


def test_autogen_adapter_unavailable():
    """When autogen is not installed, methods return None."""
    adapter = AutoGenAdapter()
    assert adapter.create_assistant_agent("a", "A", "sys") is None
    assert adapter.create_user_proxy_agent("a", "A") is None


def test_autogen_adapter_get_agent():
    adapter = AutoGenAdapter()
    assert adapter.get_agent("missing") is None


@pytest.mark.asyncio
async def test_execute_agent_workflow_missing_agent():
    result = await execute_agent_workflow(
        "wf1", ["missing_agent"], "hello"
    )
    assert result["status"] == "completed"
    assert result["results"][0]["error"] == "Agent not found"


def test_create_uar_agent_unknown_skill():
    from uar.core.exceptions import SkillNotFoundError

    with pytest.raises(SkillNotFoundError, match="not found"):
        create_uar_agent("definitely_not_a_skill_12345")


def test_autogen_available_constant():
    """AUTOGEN_AVAILABLE must be a bool."""
    assert isinstance(AUTOGEN_AVAILABLE, bool)
