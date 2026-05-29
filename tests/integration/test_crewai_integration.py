"""
Tests for CrewAI role-based multi-agent patterns integration.
"""

import pytest

from uar.core.crewai_integration import (
    AgentRole,
    AgentTask,
    RoleBasedAgent,
    TaskOrchestrator,
    get_task_orchestrator,
    create_standard_agent,
    execute_standard_workflow,
)


@pytest.mark.crewai
def test_agent_task_creation():
    """Test creating an agent task."""
    task = AgentTask(
        description="Test task",
        expected_output="Test output",
    )

    assert task.description == "Test task"
    assert task.expected_output == "Test output"
    assert task.status == "pending"
    assert task.id is not None


@pytest.mark.crewai
def test_role_based_agent_creation():
    """Test creating a role-based agent."""
    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Researcher",
        description="A test researcher agent",
    )

    assert agent.agent_id == "test_agent"
    assert agent.role == AgentRole.RESEARCHER
    assert agent.name == "Test Researcher"
    assert agent.active is True


@pytest.mark.crewai
def test_role_based_agent_task_assignment():
    """Test assigning tasks to a role-based agent."""
    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Researcher",
    )

    task = AgentTask(description="Research topic X")
    agent.assign_task(task)

    assert len(agent.assigned_tasks) == 1
    assert agent.assigned_tasks[0].agent_id == "test_agent"


@pytest.mark.crewai
def test_task_orchestrator_registration():
    """Test registering agents with task orchestrator."""
    orchestrator = TaskOrchestrator()
    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Agent",
    )

    orchestrator.register_agent(agent)

    assert orchestrator.agents["test_agent"] == agent


@pytest.mark.crewai
def test_task_orchestrator_task_creation():
    """Test creating tasks with the orchestrator."""
    orchestrator = TaskOrchestrator()

    task = orchestrator.create_task(
        description="Test task",
        expected_output="Test output",
    )

    assert task.id in orchestrator.tasks
    assert task.description == "Test task"


@pytest.mark.crewai
def test_task_orchestrator_task_assignment():
    """Test assigning tasks to specific agents."""
    orchestrator = TaskOrchestrator()
    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Agent",
    )
    orchestrator.register_agent(agent)

    task = orchestrator.create_task(description="Test task")
    orchestrator.assign_task_to_agent(task.id, "test_agent")

    assert task.agent_id == "test_agent"


@pytest.mark.crewai
def test_task_orchestrator_role_assignment():
    """Test assigning tasks by role."""
    orchestrator = TaskOrchestrator()
    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Agent",
    )
    orchestrator.register_agent(agent)

    task = orchestrator.create_task(description="Test task")
    orchestrator.assign_task_to_role(task.id, AgentRole.RESEARCHER)

    assert task.agent_id == "test_agent"


@pytest.mark.crewai
def test_task_orchestrator_status():
    """Test getting orchestrator status."""
    orchestrator = TaskOrchestrator()

    agent = RoleBasedAgent(
        agent_id="test_agent",
        role=AgentRole.RESEARCHER,
        name="Test Agent",
    )
    orchestrator.register_agent(agent)

    _ = orchestrator.create_task(description="Test task")

    status = orchestrator.get_orchestrator_status()

    assert status["agent_count"] == 1
    assert status["task_count"] == 1


@pytest.mark.crewai
def test_get_task_orchestrator_singleton():
    """Test global task orchestrator singleton."""
    orchestrator1 = get_task_orchestrator()
    orchestrator2 = get_task_orchestrator()

    assert orchestrator1 is orchestrator2


@pytest.mark.crewai
def test_create_standard_agent():
    """Test creating a standard agent."""
    agent = create_standard_agent(
        role=AgentRole.RESEARCHER,
        agent_id="researcher_1",
    )

    assert agent.role == AgentRole.RESEARCHER
    assert agent.agent_id == "researcher_1"
    assert agent.name == "Researcher"


@pytest.mark.crewai
@pytest.mark.asyncio
async def test_execute_standard_workflow():
    """Test executing a standard workflow."""
    _ = get_task_orchestrator()

    result = await execute_standard_workflow(
        workflow_type="research_analyze_write",
        input_data={"topic": "Test topic"},
    )

    assert result["status"] in ["completed", "partial"]
