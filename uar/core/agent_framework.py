"""
Microsoft Agent Framework patterns integration for UAR.

This module provides agent-to-agent communication patterns, multi-agent
orchestration, and cross-runtime interoperability inspired by Microsoft Agent
Framework (merger of AutoGen and Semantic Kernel).

Key features:
- Agent-to-agent (A2A) communication protocol
- Message passing between agents
- Agent lifecycle management
- Multi-provider model support
- Cross-runtime interoperability via MCP
"""

import inspect
import logging
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


def _utcnow() -> datetime:
    """Return a naive UTC datetime (no tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


try:
    from autogen import (  # type: ignore
        AssistantAgent,
        UserProxyAgent,
    )

    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    logging.warning(
        "AutoGen not available. Install with: pip install autogen>=0.4"
    )

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent between agents."""

    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    ERROR = "error"
    SYSTEM = "system"
    CONTROL = "control"


@dataclass
class AgentMessage:
    """A message sent between agents."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.TEXT
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    timestamp: datetime = field(default_factory=_utcnow)
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=MessageType(data["type"]),
            content=data["content"],
            metadata=data["metadata"],
            sender_id=data.get("sender_id"),
            recipient_id=data.get("recipient_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reply_to=data.get("reply_to"),
        )


@dataclass
class AgentCapability:
    """Represents a capability an agent can perform."""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None


class Agent:
    """Base agent class with A2A communication capabilities."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        capabilities: Optional[List[AgentCapability]] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = capabilities or []
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        self.active: bool = True

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[AgentMessage], Optional[AgentMessage]],
    ):
        """Register a handler for a specific message type."""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)

    async def send_message(
        self, message: AgentMessage, recipient: "Agent"
    ) -> Optional[AgentMessage]:
        """Send a message to another agent."""
        message.sender_id = self.agent_id
        message.recipient_id = recipient.agent_id

        logger.info(
            f"Agent {self.agent_id} sending {message.type.value} to "
            f"{recipient.agent_id}"
        )

        return await recipient.receive_message(message)

    async def receive_message(
        self, message: AgentMessage
    ) -> Optional[AgentMessage]:
        """Receive and process a message."""
        if not self.active:
            logger.warning("Agent %s is not active", self.agent_id)
            return AgentMessage(
                type=MessageType.ERROR,
                content="Agent is not active",
                sender_id=self.agent_id,
                reply_to=message.id,
            )

        handlers = self.message_handlers.get(message.type, [])
        response = None

        for handler in handlers:
            try:
                result = (
                    await handler(message)
                    if inspect.iscoroutinefunction(handler)
                    else handler(message)
                )
                if result:
                    response = result
            except Exception:
                logger.exception("Handler error in %s", self.agent_id)
                response = AgentMessage(
                    type=MessageType.ERROR,
                    content="Handler error",
                    sender_id=self.agent_id,
                    reply_to=message.id,
                )
                break

        return response

    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get a capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None


class AgentOrchestrator:
    """Orchestrates multi-agent workflows with A2A communication."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.message_history: List[AgentMessage] = []
        self.active_workflows: Dict[str, List[str]] = {}

    def register_agent(self, agent: Agent):
        """Register an agent with the orchestrator."""
        self.agents[agent.agent_id] = agent
        logger.info(
            "Registered agent: %s (%s)", agent.agent_id, agent.name
        )

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info("Unregistered agent: %s", agent_id)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    async def route_message(
        self, message: AgentMessage
    ) -> Optional[AgentMessage]:
        """Route a message to the appropriate agent."""
        if not message.recipient_id:
            logger.warning("Message has no recipient_id")
            return None

        recipient = self.agents.get(message.recipient_id)
        if not recipient:
            logger.warning(
                "Recipient agent not found: %s", message.recipient_id
            )
            return AgentMessage(
                type=MessageType.ERROR,
                content="Agent not found",
                sender_id="orchestrator",
            )

        self.message_history.append(message)
        return await recipient.receive_message(message)

    def start_workflow(self, workflow_id: str, agent_ids: List[str]):
        """Start a multi-agent workflow."""
        self.active_workflows[workflow_id] = agent_ids
        logger.info(
            "Started workflow %s with agents: %s", workflow_id, agent_ids
        )

    def end_workflow(self, workflow_id: str):
        """End a workflow."""
        if workflow_id in self.active_workflows:
            del self.active_workflows[workflow_id]
            logger.info("Ended workflow %s", workflow_id)

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of a workflow."""
        if workflow_id not in self.active_workflows:
            return {"status": "not_found"}

        agent_ids = self.active_workflows[workflow_id]
        agents_status = {}

        for agent_id in agent_ids:
            agent = self.agents.get(agent_id)
            if agent:
                agents_status[agent_id] = {
                    "name": agent.name,
                    "active": agent.active,
                    "capabilities": [c.name for c in agent.capabilities],
                }

        return {
            "status": "active",
            "agents": agents_status,
            "agent_count": len(agent_ids),
        }


class AutoGenAdapter:
    """Adapter for AutoGen agents to work with UAR agent framework."""

    def __init__(self):
        self.autogen_agents: Dict[str, Any] = {}

    def create_assistant_agent(
        self,
        agent_id: str,
        name: str,
        system_message: str,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Create an AutoGen assistant agent."""
        if not AUTOGEN_AVAILABLE:
            logger.error("AutoGen not available")
            return None

        try:
            agent = AssistantAgent(
                name=name,
                system_message=system_message,
                llm_config=llm_config or {},
            )
            self.autogen_agents[agent_id] = agent
            return agent
        except Exception:
            logger.exception("Failed to create AutoGen agent")
            return None

    def create_user_proxy_agent(
        self,
        agent_id: str,
        name: str,
        human_input_mode: str = "NEVER",
    ) -> Optional[Any]:
        """Create an AutoGen user proxy agent."""
        if not AUTOGEN_AVAILABLE:
            logger.error("AutoGen not available")
            return None

        try:
            agent = UserProxyAgent(
                name=name,
                human_input_mode=human_input_mode,
            )
            self.autogen_agents[agent_id] = agent
            return agent
        except Exception:
            logger.exception("Failed to create UserProxy agent")
            return None

    def get_agent(self, agent_id: str) -> Optional[Any]:
        """Get an AutoGen agent by ID."""
        return self.autogen_agents.get(agent_id)


# Global orchestrator instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get the global agent orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def create_uar_agent(
    skill_name: str,
    agent_id: Optional[str] = None,
    description: str = "",
) -> Agent:
    """Create a UAR agent from a skill."""
    if agent_id is None:
        agent_id = f"uar_{skill_name}"

    from uar.core.registry import registry

    skill = registry.get(skill_name)
    if skill is None:
        raise ValueError(f"Skill not found: {skill_name}")

    capabilities = [
        AgentCapability(
            name=skill_name,
            description=skill.__doc__ or f"Skill: {skill_name}",
        )
    ]

    return Agent(
        agent_id=agent_id,
        name=skill_name,
        description=description,
        capabilities=capabilities,
    )


async def execute_agent_workflow(
    workflow_id: str,
    agent_sequence: List[str],
    initial_message: str,
) -> Dict[str, Any]:
    """Execute a multi-agent workflow.

    Args:
        workflow_id: Unique identifier for the workflow
        agent_sequence: List of agent IDs to execute in sequence
        initial_message: Initial message to start the workflow

    Returns:
        Dictionary with workflow results
    """
    orchestrator = get_orchestrator()

    # Start workflow
    orchestrator.start_workflow(workflow_id, agent_sequence)

    results: List[Dict[str, Any]] = []
    current_message = AgentMessage(
        type=MessageType.TEXT,
        content=initial_message,
        sender_id="workflow_initiator",
    )

    for agent_id in agent_sequence:
        agent = orchestrator.get_agent(agent_id)
        if not agent:
            logger.error("Agent not found: %s", agent_id)
            results.append(
                {
                    "agent_id": agent_id,
                    "error": "Agent not found",
                }
            )
            continue

        current_message.recipient_id = agent_id
        response = await orchestrator.route_message(current_message)

        results.append(
            {
                "agent_id": agent_id,
                "message": current_message.to_dict(),
                "response": response.to_dict() if response else None,
            }
        )

        if response:
            current_message = response

    # End workflow
    orchestrator.end_workflow(workflow_id)
    return {
        "workflow_id": workflow_id,
        "agent_sequence": agent_sequence,
        "results": results,
        "status": "completed",
    }
