"""
API endpoints for advanced framework integrations.

This module provides API endpoints for the integrated frameworks:
- Multi-agent workflows
- Guardrails and governance
- Pipeline orchestration
- Knowledge graph RAG
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from uar.api.middleware import api_error_handler
logger = logging.getLogger(__name__)

# Optional advanced integrations keep runtime routes mounted, but are excluded
# from OpenAPI until broad Dict[str, Any] schemas are normalized in #116.
router = APIRouter(prefix="/api/advanced", tags=["advanced"], include_in_schema=False)


# ------------------------------------------------------------------
# Request body models for POST endpoints (previously query params)
# ------------------------------------------------------------------
class BudgetCreateReq(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    max_tokens: int = Field(100000, ge=1)
    max_api_calls: int = Field(1000, ge=1)
    max_cost_usd: float = Field(10.0, ge=0.0)
    max_duration_seconds: int = Field(3600, ge=1)


class PipelineRunReq(BaseModel):
    pipeline_name: str = Field(
        ..., description="Name of the pipeline to execute"
    )
    context: dict[str, Any] | None = Field(None)


class GraphRAGQueryReq(BaseModel):
    query: str = Field(..., description="Query string")
    strategy: str = Field("hybrid")
    top_k: int = Field(5, ge=1)


class CrewAIAgentReq(BaseModel):
    role: str = Field(..., description="Agent role")
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str | None = Field(None)
    description: str | None = Field(None)


class CrewAIWorkflowReq(BaseModel):
    workflow_type: str = Field(..., description="Type of workflow to execute")
    input_data: dict[str, Any] = Field(..., description="Workflow input data")


@router.get("/orchestrator/status")
@api_error_handler("orchestrator status")
async def get_orchestrator_status() -> Dict[str, Any]:
    """Get status of the agent orchestrator."""
    from uar.core.agent_framework import get_orchestrator

    orchestrator = get_orchestrator()
    return orchestrator.get_status()  # type: ignore


@router.get("/governance/status")
@api_error_handler("governance status")
async def get_governance_status() -> Dict[str, Any]:
    """Get status of the governance system."""
    from uar.core.guardrails import get_governance_system

    governance = get_governance_system()
    return governance.get_system_status()


@router.post("/governance/budget")
@api_error_handler("budget creation")
async def create_agent_budget(
    req: BudgetCreateReq,
) -> Dict[str, Any]:
    """Create a budget for an agent."""
    from uar.core.guardrails import get_governance_system

    governance = get_governance_system()
    budget = governance.create_budget(
        agent_id=req.agent_id,
        max_tokens=req.max_tokens,
        max_api_calls=req.max_api_calls,
        max_cost_usd=req.max_cost_usd,
        max_duration_seconds=req.max_duration_seconds,
    )
    return budget.to_dict()


@router.get("/governance/budget/{agent_id}")
@api_error_handler("budget retrieval")
async def get_agent_budget(agent_id: str) -> Dict[str, Any]:
    """Get budget status for an agent."""
    from uar.core.guardrails import get_governance_system

    governance = get_governance_system()
    budget = governance.get_budget(agent_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget.to_dict()


@router.get("/governance/violations")
@api_error_handler("violations")
async def get_violations(
    agent_id: Optional[str] = None,
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Get guardrail violations with optional filters."""
    from uar.core.guardrails import (
        ViolationSeverity,
        get_governance_system,
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


@router.get("/dagster/status")
@api_error_handler("Dagster status")
async def get_dagster_status() -> Dict[str, Any]:
    """Get status of Dagster orchestrator."""
    from uar.core.dagster_orchestration import get_orchestrator

    orchestrator = get_orchestrator()
    return orchestrator.get_orchestrator_status()


@router.post("/dagster/pipeline")
@api_error_handler("Dagster pipeline execution")
async def execute_dagster_pipeline(
    req: PipelineRunReq,
) -> Dict[str, Any]:
    """Execute a Dagster pipeline."""
    from uar.core.dagster_orchestration import get_orchestrator

    orchestrator = get_orchestrator()
    execution = orchestrator.execute_pipeline(
        req.pipeline_name,
        context=req.context or {},
    )
    return execution.to_dict()


@router.get("/graphrag/status")
@api_error_handler("GraphRAG status")
async def get_graphrag_status() -> Dict[str, Any]:
    """Get status of Flexible GraphRAG system."""
    from uar.core.flexible_graphrag import get_graphrag_instance

    graphrag = get_graphrag_instance()
    return graphrag.get_graph_stats()


@router.post("/graphrag/query")
@api_error_handler("GraphRAG query")
async def query_graphrag(
    req: GraphRAGQueryReq,
) -> Dict[str, Any]:
    """Query the knowledge graph."""
    from uar.core.flexible_graphrag import (
        SearchStrategy,
        get_graphrag_instance,
    )

    graphrag = get_graphrag_instance()

    strategy_map = {
        "vector": SearchStrategy.VECTOR,
        "fulltext": SearchStrategy.FULLTEXT,
        "property_graph": SearchStrategy.PROPERTY_GRAPH,
        "rdf_sparql": SearchStrategy.RDF_SPARQL,
        "hybrid": SearchStrategy.HYBRID,
    }
    strategy_enum = strategy_map.get(req.strategy, SearchStrategy.HYBRID)

    result = graphrag.query_graph(req.query, strategy_enum, req.top_k)
    return result


@router.get("/crewai/status")
@api_error_handler("CrewAI status")
async def get_crewai_status() -> Dict[str, Any]:
    """Get status of CrewAI task orchestrator."""
    from uar.core.crewai_integration import get_task_orchestrator

    orchestrator = get_task_orchestrator()
    return orchestrator.get_orchestrator_status()


@router.post("/crewai/agent")
@api_error_handler("CrewAI agent creation")
async def create_crewai_agent(
    req: CrewAIAgentReq,
) -> Dict[str, Any]:
    """Create a CrewAI agent with a specific role."""
    from uar.core.crewai_integration import (
        AgentRole,
        create_standard_agent,
        get_task_orchestrator,
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
    role_enum = role_map.get(req.role.lower(), AgentRole.RESEARCHER)

    agent = create_standard_agent(role=role_enum, agent_id=req.agent_id)
    if req.name:
        agent.name = req.name
    if req.description:
        agent.description = req.description

    orchestrator.register_agent(agent)

    return {
        "agent_id": agent.agent_id,
        "role": req.role,
        "name": agent.name,
        "description": agent.description,
    }


@router.post("/crewai/workflow")
@api_error_handler("CrewAI workflow execution")
async def execute_crewai_workflow(
    req: CrewAIWorkflowReq,
) -> Dict[str, Any]:
    """Execute a standard CrewAI workflow."""
    from uar.core.crewai_integration import execute_standard_workflow

    result = execute_standard_workflow(
        workflow_type=req.workflow_type,
        input_data=req.input_data,
    )
    return result  # type: ignore[return-value]
