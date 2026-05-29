"""Real CrewAI integration wrappers for UAR.

This module bridges UAR's role-based agent patterns to actual CrewAI
Agent / Task / Crew primitives when the ``crewai`` package is installed
and an LLM backend is available.

If CrewAI is missing or no LLM is configured the calling code should
fall back to ``uar.core.crewai_integration`` (UAR-native simulation).
"""

from typing import Any, Dict, List, Optional

from uar.core.crewai_integration import AgentRole


def _crewai_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("crewai") is not None


def _llm_configured() -> bool:
    """Return True if at least one LLM key is present in the environment."""
    import os

    keys = [
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "DEEPSEEK_API_KEY",
    ]
    return any(os.environ.get(k) for k in keys)


class CrewAIRealError(Exception):
    """Raised when the real CrewAI path cannot be executed."""

    pass


def _map_role_to_crewai(role: AgentRole) -> Dict[str, str]:
    """Translate UAR AgentRole into CrewAI role/goal/backstory strings."""
    mapping = {
        AgentRole.RESEARCHER: {
            "role": "Expert Researcher",
            "goal": (
                "Research and gather comprehensive information"
            ),
            "backstory": (
                "You are an expert researcher with a keen eye for detail. "
                "You excel at finding, synthesizing, and presenting "
                "information."
            ),
        },
        AgentRole.ANALYST: {
            "role": "Senior Analyst",
            "goal": (
                "Analyze data and provide actionable insights"
            ),
            "backstory": (
                "You are a skilled analyst with expertise in data "
                "interpretation and pattern recognition."
            ),
        },
        AgentRole.WRITER: {
            "role": "Professional Writer",
            "goal": "Create high-quality written content",
            "backstory": (
                "You are a professional writer with excellent communication "
                "skills and a talent for clear, engaging prose."
            ),
        },
        AgentRole.REVIEWER: {
            "role": "Quality Reviewer",
            "goal": "Review work and ensure high standards",
            "backstory": (
                "You are a meticulous reviewer with high standards. "
                "You catch issues others miss."
            ),
        },
        AgentRole.CODER: {
            "role": "Senior Software Developer",
            "goal": "Write, review, and debug code",
            "backstory": (
                "You are an expert software developer with deep knowledge "
                "of multiple programming languages and best practices."
            ),
        },
        AgentRole.PLANNER: {
            "role": "Strategic Planner",
            "goal": "Plan and organize complex projects",
            "backstory": (
                "You are a strategic planner with strong organizational "
                "skills."
            ),
        },
        AgentRole.EXECUTOR: {
            "role": "Reliable Executor",
            "goal": "Execute tasks efficiently and accurately",
            "backstory": (
                "You are a reliable executor who gets things done."
            ),
        },
        AgentRole.COORDINATOR: {
            "role": "Team Coordinator",
            "goal": "Coordinate work between agents",
            "backstory": (
                "You are an effective coordinator who ensures smooth "
                "collaboration between team members."
            ),
        },
        AgentRole.SPECIALIST: {
            "role": "Domain Specialist",
            "goal": "Apply deep domain expertise",
            "backstory": (
                "You are a specialist with deep expertise in your domain."
            ),
        },
    }
    return mapping.get(role, mapping[AgentRole.SPECIALIST])


def execute_single_task(
    role: AgentRole,
    task_description: str,
    expected_output: str = "",
    agent_name: str = "",
    tools: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Execute a single task with a CrewAI agent.

    Args:
        role: UAR agent role
        task_description: What the agent should do
        expected_output: Expected output format
        agent_name: Optional display name for the agent
        tools: Optional list of CrewAI-compatible tools

    Returns:
        Dict with status, raw_output, and metadata

    Raises:
        CrewAIRealError: If crewai is unavailable or no LLM is configured
    """
    if not _crewai_available():
        raise CrewAIRealError("crewai package is not installed")
    if not _llm_configured():
        raise CrewAIRealError("no LLM API key configured in environment")

    from crewai import Agent, Task, Crew, Process

    role_cfg = _map_role_to_crewai(role)
    agent = Agent(
        role=role_cfg["role"],
        goal=role_cfg["goal"],
        backstory=role_cfg["backstory"],
        verbose=False,
        allow_delegation=False,
        tools=tools or [],
    )

    task = Task(
        description=task_description,
        expected_output=expected_output or "A comprehensive response",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    raw = crew.kickoff()

    return {
        "status": "completed",
        "agent_role": role.value,
        "task_description": task_description,
        "raw_output": str(raw),
        "mode": "crewai_real",
    }


def execute_crew_workflow(
    task_specs: List[Dict[str, Any]],
    process: str = "sequential",
) -> Dict[str, Any]:
    """Execute a multi-step workflow with real CrewAI Crew.

    Args:
        task_specs: List of dicts with keys ``role``, ``description``,
            ``expected_output`` (and optional ``tools``)
        process: "sequential" or "hierarchical"

    Returns:
        Dict with status, raw_output, and task results

    Raises:
        CrewAIRealError: If crewai is unavailable or no LLM is configured
    """
    if not _crewai_available():
        raise CrewAIRealError("crewai package is not installed")
    if not _llm_configured():
        raise CrewAIRealError("no LLM API key configured in environment")

    from crewai import Agent, Task, Crew, Process

    agents: List[Agent] = []
    tasks: List[Task] = []

    for spec in task_specs:
        role = spec["role"]
        role_cfg = _map_role_to_crewai(role)
        agent = Agent(
            role=role_cfg["role"],
            goal=role_cfg["goal"],
            backstory=role_cfg["backstory"],
            verbose=False,
            allow_delegation=False,
            tools=spec.get("tools", []),
        )
        agents.append(agent)

        task = Task(
            description=spec["description"],
            expected_output=spec.get(
                "expected_output", "A comprehensive response"
            ),
            agent=agent,
        )
        tasks.append(task)

    process_enum = (
        Process.hierarchical
        if process == "hierarchical"
        else Process.sequential
    )

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=process_enum,
        verbose=False,
    )

    raw = crew.kickoff()

    return {
        "status": "completed",
        "mode": "crewai_real",
        "raw_output": str(raw),
        "task_count": len(tasks),
    }
