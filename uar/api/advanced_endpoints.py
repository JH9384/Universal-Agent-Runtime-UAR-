"""
API endpoints for advanced framework integrations.

This module provides API endpoints for the integrated frameworks:
- Multi-agent workflows
- Guardrails and governance
- Pipeline orchestration
- Knowledge graph RAG
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced", tags=["advanced"])


@router.get("/orchestrator/status")
async def get_orchestrator_status() -> Dict[str, Any]:
    """Get status of the agent orchestrator."""
    try:
        from uar.core.agent_framework import get_orchestrator

        orchestrator = get_orchestrator()
        return orchestrator.get_status()  # type: ignore[attr-defined,return-value]
    except Exception as e:
        logger.error(f"Failed to get orchestrator status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/governance/status")
async def get_governance_status() -> Dict[str, Any]:
    """Get status of the governance system."""
    try:
        from uar.core.guardrails import get_governance_system

        governance = get_governance_system()
        return governance.get_system_status()
    except Exception as e:
        logger.error(f"Failed to get governance status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/governance/budget")
async def create_agent_budget(
    agent_id: str,
    max_tokens: int = 100000,
    max_api_calls: int = 1000,
    max_cost_usd: float = 10.0,
    max_duration_seconds: int = 3600,
) -> Dict[str, Any]:
    """Create a budget for an agent."""
    try:
        from uar.core.guardrails import get_governance_system

        governance = get_governance_system()
        budget = governance.create_budget(
            agent_id=agent_id,
            max_tokens=max_tokens,
            max_api_calls=max_api_calls,
            max_cost_usd=max_cost_usd,
            max_duration_seconds=max_duration_seconds,
        )
        return budget.to_dict()
    except Exception as e:
        logger.error(f"Failed to create budget: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/governance/budget/{agent_id}")
async def get_agent_budget(agent_id: str) -> Dict[str, Any]:
    """Get budget status for an agent."""
    try:
        from uar.core.guardrails import get_governance_system

        governance = get_governance_system()
        budget = governance.get_budget(agent_id)
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        return budget.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get budget: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/governance/violations")
async def get_violations(
    agent_id: Optional[str] = None,
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Get guardrail violations with optional filters."""
    try:
        from uar.core.guardrails import (
            get_governance_system,
            ViolationSeverity,
        )

        governance = get_governance_system()
        severity_enum = None
        if severity:
            severity_map = {
                "info": ViolationSeverity.INFO,
                "warning": ViolationSeverity.WARNING,
                "error": ViolationSeverity.ERROR,
                "critical": ViolationSeverity.CRITICAL,
            }
            severity_enum = severity_map.get(severity.lower())

        violations = governance.guardrails.get_violations(
            agent_id=agent_id,
            severity=severity_enum,
        )
        return {
            "violations": [v.to_dict() for v in violations],
            "count": len(violations),
        }
    except Exception as e:
        logger.error(f"Failed to get violations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dagster/status")
async def get_dagster_status() -> Dict[str, Any]:
    """Get status of Dagster orchestrator."""
    try:
        from uar.core.dagster_orchestration import get_orchestrator

        orchestrator = get_orchestrator()
        return orchestrator.get_orchestrator_status()
    except Exception as e:
        logger.error(f"Failed to get Dagster status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/dagster/pipeline")
async def execute_dagster_pipeline(
    pipeline_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a Dagster pipeline."""
    try:
        from uar.core.dagster_orchestration import get_orchestrator

        orchestrator = get_orchestrator()
        execution = orchestrator.execute_pipeline(
            pipeline_name,
            context=context or {},
        )
        return execution.to_dict()
    except Exception as e:
        logger.error(f"Failed to execute pipeline: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/graphrag/status")
async def get_graphrag_status() -> Dict[str, Any]:
    """Get status of Flexible GraphRAG system."""
    try:
        from uar.core.flexible_graphrag import get_graphrag_instance

        graphrag = get_graphrag_instance()
        return graphrag.get_graph_stats()
    except Exception as e:
        logger.error(f"Failed to get GraphRAG status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/graphrag/query")
async def query_graphrag(
    query: str,
    strategy: str = "hybrid",
    top_k: int = 5,
) -> Dict[str, Any]:
    """Query the knowledge graph."""
    try:
        from uar.core.flexible_graphrag import (
            get_graphrag_instance,
            SearchStrategy,
        )

        graphrag = get_graphrag_instance()

        strategy_map = {
            "vector": SearchStrategy.VECTOR,
            "fulltext": SearchStrategy.FULLTEXT,
            "property_graph": SearchStrategy.PROPERTY_GRAPH,
            "rdf_sparql": SearchStrategy.RDF_SPARQL,
            "hybrid": SearchStrategy.HYBRID,
        }
        strategy_enum = strategy_map.get(strategy, SearchStrategy.HYBRID)

        result = graphrag.query_graph(query, strategy_enum, top_k)
        return result
    except Exception as e:
        logger.error(f"Failed to query graph: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/crewai/status")
async def get_crewai_status() -> Dict[str, Any]:
    """Get status of CrewAI task orchestrator."""
    try:
        from uar.core.crewai_integration import get_task_orchestrator

        orchestrator = get_task_orchestrator()
        return orchestrator.get_orchestrator_status()
    except Exception as e:
        logger.error(f"Failed to get CrewAI status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/crewai/agent")
async def create_crewai_agent(
    role: str,
    agent_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a CrewAI agent with a specific role."""
    try:
        from uar.core.crewai_integration import (
            get_task_orchestrator,
            create_standard_agent,
            AgentRole,
        )

        orchestrator = get_task_orchestrator()

        role_map = {
            "researcher": AgentRole.RESEARCHER,
            "analyst": AgentRole.ANALYST,
            "writer": AgentRole.WRITER,
            "reviewer": AgentRole.REVIEWER,
            "coder": AgentRole.CODER,
            "planner": AgentRole.PLANNER,
            "executor": AgentRole.EXECUTOR,
            "coordinator": AgentRole.COORDINATOR,
        }
        role_enum = role_map.get(role.lower(), AgentRole.RESEARCHER)

        agent = create_standard_agent(role=role_enum, agent_id=agent_id)
        if name:
            agent.name = name
        if description:
            agent.description = description

        orchestrator.register_agent(agent)

        return {
            "agent_id": agent.agent_id,
            "role": role,
            "name": agent.name,
            "description": agent.description,
        }
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/crewai/workflow")
async def execute_crewai_workflow(
    workflow_type: str,
    input_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a standard CrewAI workflow."""
    try:
        from uar.core.crewai_integration import execute_standard_workflow

        result = execute_standard_workflow(
            workflow_type=workflow_type,
            input_data=input_data,
        )
        return result  # type: ignore[return-value]
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
