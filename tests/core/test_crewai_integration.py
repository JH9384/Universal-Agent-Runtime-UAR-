"""Tests for crewai_integration module.

Covers AgentRole, AgentTask, RoleBasedAgent, TaskOrchestrator,
create_standard_agent, and execute_standard_workflow.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from uar.core.crewai_integration import (
    AgentRole,
    AgentTask,
    RoleBasedAgent,
    TaskOrchestrator,
    create_standard_agent,
    execute_standard_workflow,
    get_task_orchestrator,
)


class TestAgentRole:
    """AgentRole enum."""

    def test_values(self):
        assert AgentRole.RESEARCHER.value == "researcher"
        assert AgentRole.ANALYST.value == "analyst"
        assert AgentRole.WRITER.value == "writer"
        assert AgentRole.REVIEWER.value == "reviewer"
        assert AgentRole.CODER.value == "coder"
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.EXECUTOR.value == "executor"
        assert AgentRole.COORDINATOR.value == "coordinator"
        assert AgentRole.SPECIALIST.value == "specialist"


class TestAgentTask:
    """AgentTask dataclass."""

    def test_defaults(self):
        task = AgentTask()
        assert task.description == ""
        assert task.status == "pending"
        assert task.result is None
        assert isinstance(task.created_at, datetime)

    def test_to_dict(self):
        task = AgentTask(
            description="test task",
            expected_output="result",
            status="completed",
        )
        d = task.to_dict()
        assert d["description"] == "test task"
        assert d["expected_output"] == "result"
        assert d["status"] == "completed"
        assert "created_at" in d

    def test_to_dict_with_completed_at(self):
        now = datetime.now(timezone.utc)
        task = AgentTask()
        task.completed_at = now
        d = task.to_dict()
        assert d["completed_at"] == now.isoformat()


class TestRoleBasedAgent:
    """RoleBasedAgent class."""

    def test_init(self):
        agent = RoleBasedAgent(
            agent_id="a1",
            role=AgentRole.RESEARCHER,
            name="Test Agent",
            description="A test agent",
            backstory="Test backstory",
        )
        assert agent.agent_id == "a1"
        assert agent.role == AgentRole.RESEARCHER
        assert agent.name == "Test Agent"
        assert agent.backstory == "Test backstory"
        assert agent.tools == []
        assert agent.assigned_tasks == []
        assert agent.completed_tasks == []

    def test_assign_task(self):
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        task = AgentTask(description="do something")
        agent.assign_task(task)
        assert task.agent_id == "a1"
        assert task.status == "assigned"
        assert len(agent.assigned_tasks) == 1

    def test_get_status(self):
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        status = agent.get_status()
        assert status["agent_id"] == "a1"
        assert status["role"] == "researcher"
        assert status["active"] is True
        assert status["assigned_tasks"] == 0


class TestTaskOrchestrator:
    """TaskOrchestrator class."""

    def test_register_unregister_agent(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        assert "a1" in orch.agents
        orch.unregister_agent("a1")
        assert "a1" not in orch.agents

    def test_create_task(self):
        orch = TaskOrchestrator()
        task = orch.create_task("do something")
        assert task.description == "do something"
        assert task.id in orch.tasks
        assert task.id in orch.task_queue

    def test_create_task_with_role(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task = orch.create_task(
            "research", role=AgentRole.RESEARCHER
        )
        assert task.agent_id == "a1"

    def test_create_task_unknown_role_raises(self):
        orch = TaskOrchestrator()
        with pytest.raises(ValueError):
            orch.create_task("do something", role=AgentRole.RESEARCHER)

    def test_assign_task_to_agent(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task = orch.create_task("do something")
        orch.assign_task_to_agent(task.id, "a1")
        assert task.agent_id == "a1"

    def test_assign_task_to_agent_not_found(self):
        orch = TaskOrchestrator()
        task = orch.create_task("do something")
        with pytest.raises(ValueError, match="Agent not found"):
            orch.assign_task_to_agent(task.id, "unknown")

    def test_assign_task_to_role(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task = orch.create_task("do something")
        orch.assign_task_to_role(task.id, AgentRole.RESEARCHER)
        assert task.agent_id == "a1"

    def test_assign_task_to_role_no_active_agent(self):
        orch = TaskOrchestrator()
        task = orch.create_task("do something")
        with pytest.raises(ValueError, match="No active agent"):
            orch.assign_task_to_role(task.id, AgentRole.RESEARCHER)

    def test_get_task_status(self):
        orch = TaskOrchestrator()
        task = orch.create_task("do something")
        status = orch.get_task_status(task.id)
        assert status["description"] == "do something"

    def test_get_task_status_not_found(self):
        orch = TaskOrchestrator()
        assert orch.get_task_status("unknown")["error"] == "Task not found"

    def test_get_agent_status(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        status = orch.get_agent_status("a1")
        assert status["agent_id"] == "a1"

    def test_get_agent_status_not_found(self):
        orch = TaskOrchestrator()
        assert orch.get_agent_status("unknown")["error"] == "Agent not found"

    def test_get_orchestrator_status(self):
        orch = TaskOrchestrator()
        status = orch.get_orchestrator_status()
        assert status["agent_count"] == 0
        assert status["task_count"] == 0
        assert status["task_queue"] == []

    @pytest.mark.asyncio
    async def test_execute_task(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task = orch.create_task("do something")
        orch.assign_task_to_agent(task.id, "a1")
        result = await orch.execute_task(task.id)
        assert result.status == "completed"
        assert task.id in orch.completed_tasks

    @pytest.mark.asyncio
    async def test_execute_task_no_agent(self):
        orch = TaskOrchestrator()
        task = orch.create_task("do something")
        with pytest.raises(ValueError, match="no assigned agent"):
            await orch.execute_task(task.id)

    @pytest.mark.asyncio
    async def test_execute_workflow(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task1 = orch.create_task("task 1")
        orch.assign_task_to_agent(task1.id, "a1")
        result = await orch.execute_workflow([task1.id])
        assert result["status"] == "completed"
        assert task1.id in result["executed"]

    @pytest.mark.asyncio
    async def test_execute_workflow_with_dependencies(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task1 = orch.create_task("task 1")
        task2 = orch.create_task("task 2", dependencies=[task1.id])
        orch.assign_task_to_agent(task1.id, "a1")
        orch.assign_task_to_agent(task2.id, "a1")
        result = await orch.execute_workflow([task1.id, task2.id])
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_workflow_circular_dependency(self):
        orch = TaskOrchestrator()
        agent = RoleBasedAgent(
            agent_id="a1", role=AgentRole.RESEARCHER, name="Test"
        )
        orch.register_agent(agent)
        task1 = orch.create_task("task 1", dependencies=["nonexistent"])
        orch.assign_task_to_agent(task1.id, "a1")
        result = await orch.execute_workflow([task1.id])
        assert result["status"] == "partial"


class TestCreateStandardAgent:
    """create_standard_agent function."""

    def test_researcher(self):
        agent = create_standard_agent(AgentRole.RESEARCHER)
        assert agent.role == AgentRole.RESEARCHER
        assert agent.name == "Researcher"
        assert "expert researcher" in agent.backstory

    def test_analyst(self):
        agent = create_standard_agent(AgentRole.ANALYST)
        assert agent.role == AgentRole.ANALYST
        assert agent.name == "Analyst"

    def test_writer(self):
        agent = create_standard_agent(AgentRole.WRITER)
        assert agent.role == AgentRole.WRITER
        assert agent.name == "Writer"

    def test_reviewer(self):
        agent = create_standard_agent(AgentRole.REVIEWER)
        assert agent.role == AgentRole.REVIEWER
        assert agent.name == "Reviewer"

    def test_coder(self):
        agent = create_standard_agent(AgentRole.CODER)
        assert agent.role == AgentRole.CODER
        assert agent.name == "Coder"

    def test_planner(self):
        agent = create_standard_agent(AgentRole.PLANNER)
        assert agent.role == AgentRole.PLANNER
        assert agent.name == "Planner"

    def test_executor(self):
        agent = create_standard_agent(AgentRole.EXECUTOR)
        assert agent.role == AgentRole.EXECUTOR
        assert agent.name == "Executor"

    def test_coordinator(self):
        agent = create_standard_agent(AgentRole.COORDINATOR)
        assert agent.role == AgentRole.COORDINATOR
        assert agent.name == "Coordinator"

    def test_specialist_fallback(self):
        agent = create_standard_agent(AgentRole.SPECIALIST)
        assert agent.role == AgentRole.SPECIALIST
        assert "specialist agent" in agent.backstory

    def test_custom_name(self):
        agent = create_standard_agent(
            AgentRole.RESEARCHER, name="Custom"
        )
        assert agent.name == "Custom"

    def test_custom_description(self):
        agent = create_standard_agent(
            AgentRole.RESEARCHER, description="Custom desc"
        )
        assert agent.description == "Custom desc"

    def test_custom_backstory(self):
        agent = create_standard_agent(
            AgentRole.RESEARCHER, backstory="Custom story"
        )
        assert agent.backstory == "Custom story"

    def test_auto_agent_id(self):
        agent = create_standard_agent(AgentRole.RESEARCHER)
        assert agent.agent_id.startswith("researcher_")


class TestExecuteStandardWorkflow:
    """execute_standard_workflow function."""

    @pytest.mark.asyncio
    async def test_research_analyze_write(self):
        with patch(
            "uar.core.crewai_integration.get_task_orchestrator",
            return_value=TaskOrchestrator(),
        ):
            result = await execute_standard_workflow(
                "research_analyze_write", {"topic": "AI"}
            )
        assert "task_ids" in result
        assert "results" in result
        assert result["status"] in ("completed", "partial")

    @pytest.mark.asyncio
    async def test_code_review(self):
        with patch(
            "uar.core.crewai_integration.get_task_orchestrator",
            return_value=TaskOrchestrator(),
        ):
            result = await execute_standard_workflow(
                "code_review", {"code": "print(1)"}
            )
        assert "task_ids" in result

    @pytest.mark.asyncio
    async def test_data_analysis(self):
        with patch(
            "uar.core.crewai_integration.get_task_orchestrator",
            return_value=TaskOrchestrator(),
        ):
            result = await execute_standard_workflow(
                "data_analysis", {"data": [1, 2, 3]}
            )
        assert "task_ids" in result

    @pytest.mark.asyncio
    async def test_unknown_workflow(self):
        with pytest.raises(ValueError, match="Unknown workflow"):
            await execute_standard_workflow("unknown", {})


class TestGetTaskOrchestrator:
    """get_task_orchestrator singleton."""

    def test_returns_same_instance(self):
        orch1 = get_task_orchestrator()
        orch2 = get_task_orchestrator()
        assert orch1 is orch2

    def test_is_task_orchestrator(self):
        orch = get_task_orchestrator()
        assert isinstance(orch, TaskOrchestrator)
