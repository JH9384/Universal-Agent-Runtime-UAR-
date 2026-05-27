"""
CrewAI role-based multi-agent patterns integration for UAR.

This module provides role-based agent orchestration inspired by CrewAI,
enabling specialized agents with clear role definitions, task delegation,
and collaboration patterns.

Key features:
- Role-based agent design (researcher, writer, analyst, etc.)
- Task delegation and collaboration patterns
- Built-in memory and context management
- Hierarchical task execution
- Agent specialization patterns
"""

import importlib.util
import logging
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from uar.core.agent_framework import Agent

CREWAI_AVAILABLE = importlib.util.find_spec("crewai") is not None
if not CREWAI_AVAILABLE:
    logging.warning(
        "CrewAI not available. Install with: pip install crewai>=0.80"
    )


logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Predefined agent roles for common use cases."""

    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    REVIEWER = "reviewer"
    CODER = "coder"
    PLANNER = "planner"
    EXECUTOR = "executor"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"


@dataclass
class AgentTask:
    """Represents a task that can be assigned to an agent."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    expected_output: str = ""
    agent_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_id": self.agent_id,
            "context": self.context,
            "dependencies": self.dependencies,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class RoleBasedAgent(Agent):
    """Agent with specific role and capabilities."""

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        name: str,
        description: str = "",
        backstory: str = "",
        tools: Optional[List[str]] = None,
        verbose: bool = False,
        allow_delegation: bool = False,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
        )
        self.role = role
        self.backstory = backstory
        self.tools = tools or []
        self.verbose = verbose
        self.allow_delegation = allow_delegation
        self.assigned_tasks: List[AgentTask] = []
        self.completed_tasks: List[AgentTask] = []

    def assign_task(self, task: AgentTask):
        """Assign a task to this agent."""
        task.agent_id = self.agent_id
        task.status = "assigned"
        self.assigned_tasks.append(task)
        logger.info(f"Task {task.id} assigned to agent {self.agent_id}")

    async def execute_task(self, task: AgentTask) -> AgentTask:
        """Execute a task and return the result."""
        task.status = "in_progress"
        logger.info(f"Agent {self.agent_id} executing task {task.id}")

        try:
            # Execute the task based on the agent's capabilities
            result = await self._perform_task(task)
            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

            self.assigned_tasks.remove(task)
            self.completed_tasks.append(task)

            logger.info(f"Task {task.id} completed by agent {self.agent_id}")

        except Exception as e:
            task.status = "failed"
            task.result = {"error": "Task failed"}
            logger.error(f"Task {task.id} failed: {e}")

        return task

    async def _perform_task(self, task: AgentTask) -> Any:
        """Perform the actual task execution."""
        # This is a placeholder - actual implementation depends on the role
        # and the specific task being executed
        return {
            "task_id": task.id,
            "agent_id": self.agent_id,
            "role": self.role.value,
            "result": f"Task executed by {self.role.value} agent",
        }

    def get_status(self) -> Dict[str, Any]:
        """Get the agent's current status."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "active": self.active,
            "assigned_tasks": len(self.assigned_tasks),
            "completed_tasks": len(self.completed_tasks),
            "tools": self.tools,
        }


class TaskOrchestrator:
    """Orchestrates task execution across multiple role-based agents."""

    def __init__(self):
        self.agents: Dict[str, RoleBasedAgent] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.task_queue: List[str] = []
        self.completed_tasks: List[str] = []

    def register_agent(self, agent: RoleBasedAgent):
        """Register a role-based agent."""
        self.agents[agent.agent_id] = agent
        logger.info(
            f"Registered agent: {agent.agent_id} with role {agent.role.value}"
        )

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")

    def create_task(
        self,
        description: str,
        expected_output: str = "",
        context: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        role: Optional[AgentRole] = None,
    ) -> AgentTask:
        """Create a new task."""
        task = AgentTask(
            description=description,
            expected_output=expected_output,
            context=context or {},
            dependencies=dependencies or [],
        )
        self.tasks[task.id] = task
        self.task_queue.append(task.id)

        # Auto-assign to agent if role is specified
        if role:
            self.assign_task_to_role(task.id, role)

        return task

    def assign_task_to_role(self, task_id: str, role: AgentRole):
        """Assign a task to an agent with a specific role."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Find an agent with the specified role
        for agent in self.agents.values():
            if agent.role == role and agent.active:
                agent.assign_task(task)
                logger.info(
                    f"Task {task_id} assigned to {agent.agent_id} (role: {role.value})"  # noqa: E501
                )
                return

        raise ValueError(f"No active agent found with role: {role.value}")

    def assign_task_to_agent(self, task_id: str, agent_id: str):
        """Assign a task to a specific agent."""
        task = self.tasks.get(task_id)
        agent = self.agents.get(agent_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        agent.assign_task(task)
        logger.info(f"Task {task_id} assigned to agent {agent_id}")

    async def execute_task(self, task_id: str) -> AgentTask:
        """Execute a specific task."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if not task.agent_id:
            raise ValueError(f"Task {task_id} has no assigned agent")

        agent = self.agents.get(task.agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {task.agent_id}")

        result = await agent.execute_task(task)

        if task.status == "completed":
            self.completed_tasks.append(task_id)

        return result

    async def execute_workflow(
        self,
        task_ids: List[str],
    ) -> Dict[str, Any]:
        """Execute a workflow of tasks with dependency resolution."""
        results: Dict[str, Any] = {}
        executed: set[str] = set()

        while len(executed) < len(task_ids):
            progress = False

            for task_id in task_ids:
                if task_id in executed:
                    continue

                task = self.tasks.get(task_id)
                if not task:
                    continue

                # Check if dependencies are met
                dependencies_met = all(
                    dep in executed for dep in task.dependencies
                )

                if not dependencies_met:
                    continue

                # Execute the task
                result = await self.execute_task(task_id)
                results[task_id] = result.to_dict()
                executed.add(task_id)
                progress = True

            if not progress:
                # Circular dependency or missing dependency
                pending = [tid for tid in task_ids if tid not in executed]
                logger.error(
                    f"Cannot resolve dependencies for tasks: {pending}"
                )
                break

        return {
            "task_ids": task_ids,
            "results": results,
            "executed": list(executed),
            "status": "completed"
            if len(executed) == len(task_ids)
            else "partial",
        }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}

        return task.to_dict()

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get the status of an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}

        return agent.get_status()

    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get the overall status of the orchestrator."""
        return {
            "agents": {
                agent_id: agent.get_status()
                for agent_id, agent in self.agents.items()
            },
            "tasks": {
                task_id: task.to_dict() for task_id, task in self.tasks.items()
            },
            "task_queue": self.task_queue,
            "completed_tasks": self.completed_tasks,
            "agent_count": len(self.agents),
            "task_count": len(self.tasks),
        }


# Global orchestrator instance
_task_orchestrator: Optional[TaskOrchestrator] = None


def get_task_orchestrator() -> TaskOrchestrator:
    """Get the global task orchestrator instance."""
    global _task_orchestrator
    if _task_orchestrator is None:
        _task_orchestrator = TaskOrchestrator()
    return _task_orchestrator


def create_standard_agent(
    role: AgentRole,
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    backstory: Optional[str] = None,
) -> RoleBasedAgent:
    """Create a standard agent with predefined role configuration."""
    if agent_id is None:
        agent_id = f"{role.value}_{uuid.uuid4().hex[:8]}"

    if name is None:
        name = role.value.title()

    # Default descriptions and backstories for common roles
    role_configs = {
        AgentRole.RESEARCHER: {
            "description": "Researches and gathers information",
            "backstory": "You are an expert researcher with a keen eye for detail",  # noqa: E501
        },
        AgentRole.ANALYST: {
            "description": "Analyzes data and provides insights",
            "backstory": "You are a skilled analyst with expertise in data interpretation",  # noqa: E501
        },
        AgentRole.WRITER: {
            "description": "Writes and edits content",
            "backstory": "You are a professional writer with excellent communication skills",  # noqa: E501
        },
        AgentRole.REVIEWER: {
            "description": "Reviews and validates work",
            "backstory": "You are a meticulous reviewer with high standards",
        },
        AgentRole.CODER: {
            "description": "Writes and reviews code",
            "backstory": "You are an expert software developer",
        },
        AgentRole.PLANNER: {
            "description": "Plans and organizes work",
            "backstory": "You are a strategic planner with strong organizational skills",  # noqa: E501
        },
        AgentRole.EXECUTOR: {
            "description": "Executes tasks efficiently",
            "backstory": "You are a reliable executor who gets things done",
        },
        AgentRole.COORDINATOR: {
            "description": "Coordinates work between agents",
            "backstory": "You are an effective coordinator who ensures smooth collaboration",  # noqa: E501
        },
    }

    config = role_configs.get(
        role,
        {
            "description": f"{role.value} agent",
            "backstory": f"You are a {role.value} agent",
        },
    )

    return RoleBasedAgent(
        agent_id=agent_id,
        role=role,
        name=name,
        description=description or config["description"],
        backstory=backstory or config["backstory"],
    )


async def execute_standard_workflow(
    workflow_type: str,
    input_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a standard multi-agent workflow.

    Args:
        workflow_type: Type of workflow (e.g., "research_analyze_write")
        input_data: Input data for the workflow

    Returns:
        Dictionary with workflow results
    """
    orchestrator = get_task_orchestrator()

    # Define standard workflow templates
    workflows = {
        "research_analyze_write": [
            (AgentRole.RESEARCHER, "Research the topic"),
            (AgentRole.ANALYST, "Analyze the research findings"),
            (AgentRole.WRITER, "Write a comprehensive report"),
        ],
        "code_review": [
            (AgentRole.CODER, "Review the code"),
            (AgentRole.REVIEWER, "Validate the review"),
        ],
        "data_analysis": [
            (AgentRole.ANALYST, "Analyze the data"),
            (AgentRole.RESEARCHER, "Research anomalies"),
            (AgentRole.WRITER, "Write analysis report"),
        ],
    }

    workflow = workflows.get(workflow_type)
    if not workflow:
        raise ValueError(f"Unknown workflow type: {workflow_type}")

    # Create agents if they don't exist
    for role, description in workflow:
        agent_id = f"{role.value}_standard"
        if agent_id not in orchestrator.agents:
            agent = create_standard_agent(role, agent_id)
            orchestrator.register_agent(agent)

    # Create tasks
    task_ids: list[str] = []
    for i, (role, description) in enumerate(workflow):
        task = orchestrator.create_task(
            description=description,
            context=input_data,
            dependencies=task_ids[-1:] if i > 0 else [],
            role=role,
        )
        task_ids.append(task.id)

    # Execute workflow
    result = await orchestrator.execute_workflow(task_ids)

    return result
