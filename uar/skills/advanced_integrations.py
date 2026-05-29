"""
Skill wrapper functions for advanced framework integrations.

This module provides UAR skill wrappers for the integrated frameworks:
- Microsoft Agent Framework (agent workflows)
- CrewAI (role-based multi-agent patterns)
- LlamaIndex (advanced RAG)
- Dagster (pipeline orchestration)
- Guardrails (governance)
- Flexible GraphRAG (knowledge graph RAG)
"""

from pathlib import Path
from typing import Any, Dict
from uar.core.async_utils import run_sync_safe
from uar.core.registry import register_skill
from uar.core.skill_utils import require_package, skill_guard


@register_skill("agent_workflow")
@skill_guard("Agent Workflow")
def agent_workflow(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute multi-agent workflows using Microsoft Agent Framework patterns.

    This skill orchestrates multiple agents to collaborate on a task,
    using agent-to-agent communication and coordination patterns.

    Metadata:
        - agent_sequence: List of agent IDs to execute in order
        - workflow_type: Type of workflow (default: "sequential")
        - initial_message: Starting message for the workflow

    Returns:
        Dict with workflow execution results including:
        - workflow_id: Unique workflow identifier
        - status: Workflow status (completed, partial, failed)
        - results: Results from each agent in the sequence
    """
    from uar.core.agent_framework import (
        execute_agent_workflow,
        get_orchestrator,
    )

    orchestrator = get_orchestrator()

    # Get metadata
    metadata = ctx.get("metadata", {})
    agent_sequence = metadata.get("agent_sequence", ["agent1", "agent2"])
    workflow_type = metadata.get("workflow_type", "sequential")
    initial_message = metadata.get("initial_message", ctx.get("goal", ""))

    # Register agents if provided
    agents = metadata.get("agents", [])
    for agent_config in agents:
        from uar.core.agent_framework import Agent

        agent = Agent(
            agent_id=agent_config.get("id"),
            name=agent_config.get("name", agent_config.get("id")),
            description=agent_config.get("description", ""),
        )
        orchestrator.register_agent(agent)

    # Execute workflow (async function called safely from sync skill)
    result = run_sync_safe(execute_agent_workflow(
        workflow_id=f"workflow_{workflow_type}",
        agent_sequence=agent_sequence,
        initial_message=initial_message,
    ))

    return {
        "status": "success",
        "workflow_id": result["workflow_id"],
        "workflow_type": workflow_type,
        "agent_sequence": agent_sequence,
        "results": result.get("results", []),
        "status_code": result.get("status"),
    }


@register_skill("crewai_task")
@skill_guard("Crewai Task")
def crewai_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute role-based agent tasks using CrewAI patterns.

    When CrewAI is installed and an LLM is configured the task is
    executed by a real CrewAI agent.  Otherwise a UAR-native role
    simulation is used and the result is tagged ``mode: uar_native``
    so callers know exactly what happened.

    Metadata:
        - role: Agent role (researcher, analyst, writer, etc.)
        - task_description: Description of the task to execute
        - expected_output: Expected output format

    Returns:
        Dict with task execution results
    """
    from uar.core.crewai_integration import (
        CREWAI_AVAILABLE,
        TaskOrchestrator,
        create_standard_agent,
        AgentRole,
    )

    # Get metadata
    metadata = ctx.get("metadata", {})
    role_str = metadata.get("role", "researcher")
    task_description = metadata.get(
        "task_description", ctx.get("goal", "")
    )
    expected_output = metadata.get("expected_output", "")

    # Map role string to enum
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
    role = role_map.get(role_str.lower(), AgentRole.RESEARCHER)

    # Try real CrewAI first
    if CREWAI_AVAILABLE:
        try:
            from uar.core.crewai_real import (
                execute_single_task,
                CrewAIRealError,
            )

            result = execute_single_task(
                role=role,
                task_description=task_description,
                expected_output=expected_output,
            )
            result["skill"] = "crewai_task"
            result["role"] = role_str
            return result
        except CrewAIRealError:
            pass

    # UAR-native fallback
    orchestrator = TaskOrchestrator()
    agent = create_standard_agent(role=role)
    orchestrator.register_agent(agent)
    task = orchestrator.create_task(
        description=task_description,
        expected_output=expected_output,
    )
    orchestrator.assign_task_to_agent(task.id, agent.agent_id)
    executed = run_sync_safe(orchestrator.execute_task(task.id))

    return {
        "status": "completed" if executed.status == "completed" else "failed",
        "agent_id": agent.agent_id,
        "role": role_str,
        "task_id": task.id,
        "task_description": task_description,
        "mode": "uar_native",
        "result": executed.result if executed.result else {},
    }


@register_skill("crewai_workflow")
@skill_guard("Crewai Workflow")
def crewai_workflow(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute standard multi-agent workflows using CrewAI patterns.

    When CrewAI is installed and an LLM is configured the workflow is
    executed by real CrewAI Crews.  Otherwise the UAR-native
    TaskOrchestrator simulation is used and the result is tagged
    ``mode: uar_native``.

    Metadata:
        - workflow_type: Type of workflow to execute
        - input_data: Input data for the workflow

    Returns:
        Dict with workflow execution results
    """
    from uar.core.crewai_integration import (
        CREWAI_AVAILABLE,
        AgentRole,
        execute_standard_workflow,
    )

    # Get metadata
    metadata = ctx.get("metadata", {})
    workflow_type = metadata.get("workflow_type", "research_analyze_write")
    input_data = metadata.get("input_data", {"topic": ctx.get("goal", "")})

    # Try real CrewAI first
    if CREWAI_AVAILABLE:
        try:
            from uar.core.crewai_real import (
                execute_crew_workflow,
                CrewAIRealError,
            )

            workflow_map = {
                "research_analyze_write": [
                    {
                        "role": AgentRole.RESEARCHER,
                        "description": "Research the topic",
                        "expected_output": "Research findings",
                    },
                    {
                        "role": AgentRole.ANALYST,
                        "description": "Analyze the research findings",
                        "expected_output": "Analysis report",
                    },
                    {
                        "role": AgentRole.WRITER,
                        "description": "Write a comprehensive report",
                        "expected_output": "Final report",
                    },
                ],
                "code_review": [
                    {
                        "role": AgentRole.CODER,
                        "description": "Review the code",
                        "expected_output": "Code review notes",
                    },
                    {
                        "role": AgentRole.REVIEWER,
                        "description": "Validate the review",
                        "expected_output": "Validation result",
                    },
                ],
                "data_analysis": [
                    {
                        "role": AgentRole.ANALYST,
                        "description": "Analyze the data",
                        "expected_output": "Data analysis",
                    },
                    {
                        "role": AgentRole.RESEARCHER,
                        "description": "Research anomalies",
                        "expected_output": "Anomaly research",
                    },
                    {
                        "role": AgentRole.WRITER,
                        "description": "Write analysis report",
                        "expected_output": "Analysis report",
                    },
                ],
            }
            task_specs = workflow_map.get(workflow_type, [])
            if task_specs:
                result = execute_crew_workflow(
                    task_specs=task_specs,
                    process="sequential",
                )
                result["skill"] = "crewai_workflow"
                result["workflow_type"] = workflow_type
                return result
        except CrewAIRealError:
            pass

    # UAR-native fallback
    result = run_sync_safe(execute_standard_workflow(
        workflow_type=workflow_type,
        input_data=input_data,
    ))

    status = (
        "completed" if result.get("status") == "completed" else "partial"
    )
    return {
        "status": status,
        "workflow_id": result.get("task_ids", []),
        "workflow_type": workflow_type,
        "agent_sequence": result.get("agent_sequence", []),
        "status_code": result.get("status"),
        "results": result.get("results", []),
        "mode": "uar_native",
    }


@register_skill("llamaindex_rag")
@skill_guard("Llamaindex Rag")
def llamaindex_rag(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute advanced RAG using LlamaIndex capabilities.

    Requires ``llama-index``.  Falls back to UAR-native RAG when
    unavailable and reports ``mode: uar_native``.

    This skill provides advanced retrieval-augmented generation with
    hierarchical chunking, hybrid search, and knowledge graph support.

    Metadata:
        - chunking_strategy: Chunking strategy (fixed, hierarchical, semantic)
        - retrieval_strategy: Retrieval strategy (vector, bm25, hybrid, etc.)
        - chunk_size: Size of chunks (default: 512)
        - top_k: Number of top results to retrieve (default: 5)

    Returns:
        Dict with RAG query results
    """
    err = require_package("llama_index")
    if err:
        return err

    from uar.core.llamaindex_rag import (
        LlamaIndexRAG,
        RAGConfig,
        ChunkingStrategy,
        RetrievalStrategy,
    )

    # Get metadata
    metadata = ctx.get("metadata", {})
    chunking_str = metadata.get("chunking_strategy", "hierarchical")
    retrieval_str = metadata.get("retrieval_strategy", "hybrid")
    chunk_size = metadata.get("chunk_size", 512)
    top_k = metadata.get("top_k", 5)

    # Map strings to enums
    chunking_map = {
        "fixed": ChunkingStrategy.FIXED,  # type: ignore[attr-defined]
        "hierarchical": ChunkingStrategy.HIERARCHICAL,
        "semantic": ChunkingStrategy.SEMANTIC,
    }
    retrieval_map = {
        "vector": RetrievalStrategy.VECTOR,
        "bm25": RetrievalStrategy.BM25,
        "hybrid": RetrievalStrategy.HYBRID,
        "auto_merging": RetrievalStrategy.AUTO_MERGING,
        "knowledge_graph": RetrievalStrategy.KNOWLEDGE_GRAPH,
    }

    chunking_strategy = chunking_map.get(
        chunking_str, ChunkingStrategy.HIERARCHICAL
    )
    retrieval_strategy = retrieval_map.get(
        retrieval_str, RetrievalStrategy.HYBRID
    )

    # Create RAG config
    config = RAGConfig(
        chunking_strategy=chunking_strategy,
        retrieval_strategy=retrieval_strategy,
        chunk_size=chunk_size,
        top_k=top_k,
    )

    # Create RAG instance
    rag = LlamaIndexRAG(config)

    # Load documents if input_path is provided
    input_path = ctx.get("input_path")
    if input_path:
        rag.load_documents(input_path)
        rag.create_index()

    # Execute query
    query = ctx.get("goal", "")
    result = rag.query(query)

    return {
        "status": "completed",
        "query": query,
        "response": result.response,
        "sources": [
            node.to_dict() for node in result.retrieved_nodes
        ],
        "metadata": result.metadata,
    }


@register_skill("llamaindex_query")
@skill_guard("Llamaindex Query")
def llamaindex_query(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query an existing LlamaIndex RAG system.

    This skill queries a previously created LlamaIndex RAG index
    using multiple retrieval strategies.

    Metadata:
        - retrieval_strategy: Retrieval strategy to use
        - top_k: Number of results to retrieve

    Returns:
        Dict with query results
    """
    err = require_package("llama_index")
    if err:
        return err

    from uar.core.llamaindex_rag import get_rag_instance, RetrievalStrategy

    # Get metadata
    metadata = ctx.get("metadata", {})
    retrieval_str = metadata.get("retrieval_strategy", "hybrid")
    top_k = metadata.get("top_k", 5)

    retrieval_map = {
        "vector": RetrievalStrategy.VECTOR,
        "bm25": RetrievalStrategy.BM25,
        "hybrid": RetrievalStrategy.HYBRID,
        "auto_merging": RetrievalStrategy.AUTO_MERGING,
        "knowledge_graph": RetrievalStrategy.KNOWLEDGE_GRAPH,
    }
    retrieval_strategy = retrieval_map.get(
        retrieval_str, RetrievalStrategy.HYBRID
    )

    # Get RAG instance
    rag = get_rag_instance()

    # Execute query
    query = ctx.get("goal", "")
    result = rag.query(  # type: ignore[call-arg]
        query, retrieval_strategy=retrieval_strategy, top_k=top_k
    )

    return {
        "status": "completed",
        "query": query,
        "response": result.response,
        "sources": [
            node.to_dict() for node in result.retrieved_nodes
        ],
        "metadata": result.metadata,
    }


@register_skill("dagster_pipeline")
@skill_guard("Dagster Pipeline")
def dagster_pipeline(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Dagster pipelines with asset-based orchestration.

    This skill executes Dagster pipelines for data orchestration,
    with asset tracking and observability.

    Metadata:
        - pipeline_name: Name of the pipeline to execute
        - context: Additional context for pipeline execution

    Returns:
        Dict with pipeline execution results
    """
    err = require_package("dagster")
    if err:
        return err

    from uar.core.dagster_orchestration import (
        get_orchestrator,
        create_standard_pipelines,
    )

    # Get metadata
    metadata = ctx.get("metadata", {})
    pipeline_name = metadata.get("pipeline_name", "rag_pipeline")
    context = metadata.get("context", {})

    # Setup standard pipelines
    create_standard_pipelines()

    # Get orchestrator
    orchestrator = get_orchestrator()

    # Execute pipeline
    execution = orchestrator.execute_pipeline(pipeline_name, context)

    return {
        "status": "completed",
        "execution_id": execution.execution_id,
        "pipeline_name": execution.pipeline_name,
        "status_code": execution.status.value,
        "assets_produced": execution.assets_produced,
        "assets_consumed": execution.assets_consumed,
        "metadata": execution.metadata,
    }


@register_skill("dagster_status")
@skill_guard("Dagster Status")
def dagster_status(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check Dagster pipeline and asset status.

    This skill provides status information about Dagster pipelines,
    assets, and executions.

    Returns:
        Dict with pipeline and asset status
    """
    err = require_package("dagster")
    if err:
        return err

    from uar.core.dagster_orchestration import get_orchestrator

    orchestrator = get_orchestrator()
    status = orchestrator.get_orchestrator_status()

    return {
        "status": "completed",
        "orchestrator_status": status,
    }


@register_skill("guardrail_check")
@skill_guard("Guardrail Check")
def guardrail_check(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check guardrails for agent outputs.

    This skill validates content against guardrails including
    content safety, rate limits, budgets, and compliance.

    Metadata:
        - guardrail_type: Type of guardrail to check
        - content: Content to validate

    Returns:
        Dict with guardrail check results and any violations
    """
    from uar.core.guardrails import (
        get_governance_system,
        setup_default_guardrails,
        GuardrailType,
    )

    # Setup default guardrails
    setup_default_guardrails()

    # Get governance system
    governance = get_governance_system()

    # Get metadata
    metadata = ctx.get("metadata", {})
    guardrail_str = metadata.get("guardrail_type", "content_safety")
    content = metadata.get("content", ctx.get("goal", ""))

    guardrail_map = {
        "content_safety": GuardrailType.CONTENT_SAFETY,
        "rate_limit": GuardrailType.RATE_LIMIT,
        "budget": GuardrailType.BUDGET,
        "permission": GuardrailType.PERMISSION,
        "compliance": GuardrailType.COMPLIANCE,
        "output_validation": GuardrailType.OUTPUT_VALIDATION,
    }
    guardrail_type = guardrail_map.get(
        guardrail_str, GuardrailType.CONTENT_SAFETY
    )

    # Check guardrails
    violations = governance.guardrails.check(
        agent_id="system",
        guardrail_type=guardrail_type,
        data=content,
    )

    return {
        "status": "success",
        "guardrail_type": guardrail_str,
        "violations": [v.to_dict() for v in violations],
        "violation_count": len(violations),
        "passed": len(violations) == 0,
    }


@register_skill("budget_status")
@skill_guard("Budget Status")
def budget_status(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check agent budget status.

    This skill provides information about agent budgets including
    tokens, API calls, cost, and time limits.

    Metadata:
        - agent_id: ID of the agent to check (default: "system")

    Returns:
        Dict with budget status information
    """
    from uar.core.guardrails import get_governance_system

    governance = get_governance_system()

    # Get metadata
    metadata = ctx.get("metadata", {})
    agent_id = metadata.get("agent_id", "system")

    # Get or create budget
    budget = governance.get_budget(agent_id)
    if not budget:
        from uar.core.guardrails import Budget

        budget = Budget(agent_id=agent_id)
        governance.budgets[agent_id] = budget

    return {
        "status": "success",
        "agent_id": agent_id,
        "budget": budget.to_dict(),
    }


@register_skill("blackboard_status")
@skill_guard("Blackboard Status")
def blackboard_status(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check shared blackboard status for agent coordination.

    This skill provides information about the shared blackboard
    used for agent coordination and communication.

    Returns:
        Dict with blackboard status information
    """
    from uar.core.guardrails import get_governance_system

    governance = get_governance_system()
    status = governance.blackboard.get_status()

    return {
        "status": "success",
        "blackboard_status": status,
    }


@register_skill("flexible_graphrag")
@skill_guard("Flexible Graphrag")
def flexible_graphrag(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Flexible GraphRAG with multiple backends and hybrid search.

    This skill provides knowledge graph RAG with support for multiple
    graph database backends and hybrid semantic search strategies.

    Metadata:
        - backend: Graph backend (neo4j, memgraph, rdf, in_memory)
        - search_strategy: Search strategy (vector, fulltext, property_graph, hybrid)
        - top_k: Number of results to retrieve

    Returns:
        Dict with graph query results
    """  # noqa: E501
    err = require_package("rdflib")
    if err:
        return err

    from uar.core.flexible_graphrag import (
        GraphBackend,
        SearchStrategy,
        get_graphrag_instance,
    )

    # Get metadata
    metadata = ctx.get("metadata", {})
    backend_str = metadata.get("backend", "in_memory")
    search_str = metadata.get("search_strategy", "hybrid")
    top_k = metadata.get("top_k", 5)

    # Map strings to enums
    backend_map = {
        "neo4j": GraphBackend.NEO4J,
        "memgraph": GraphBackend.MEMGRAPH,
        "rdf": GraphBackend.RDF,
        "in_memory": GraphBackend.IN_MEMORY,
    }
    search_map = {
        "vector": SearchStrategy.VECTOR,
        "fulltext": SearchStrategy.FULLTEXT,
        "property_graph": SearchStrategy.PROPERTY_GRAPH,
        "rdf_sparql": SearchStrategy.RDF_SPARQL,
        "hybrid": SearchStrategy.HYBRID,
    }

    backend = backend_map.get(backend_str, GraphBackend.IN_MEMORY)
    search_strategy = search_map.get(search_str, SearchStrategy.HYBRID)

    # Get or create graphrag instance
    graphrag = get_graphrag_instance(backend=backend)

    # Build graph from documents if input_path is provided
    input_path = ctx.get("input_path")
    if input_path:
        from uar.skills.doc_ingest import _yield_documents

        documents = list(
            _yield_documents(
                Path(input_path),
                allowed_root=Path(input_path),
            )
        )
        graphrag.build_graph_from_documents(documents)

    # Query the graph
    query = ctx.get("goal", "")
    result = graphrag.query_graph(
        query, strategy=search_strategy, top_k=top_k
    )

    return {
        "status": "completed",
        "query": query,
        "backend": backend_str,
        "search_strategy": search_str,
        "results": result["results"],
        "result_count": result["result_count"],
    }


# ---------------------------------------------------------------------------
# Multi-Agent Blackboard Communication
# ---------------------------------------------------------------------------


@register_skill("blackboard_message")
def blackboard_message(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Post or read messages on a shared blackboard for inter-agent comms.

    This skill enables agents to communicate via a shared key-value
    store within the pipeline context.  It is the foundational
    primitive for multi-agent coordination.

    Metadata:
      action      — "post" | "read" | "list" (default "read")
      channel     — blackboard channel name (default "default")
      key         — message key (required for post/read)
      value       — message payload (required for post)
    """
    goal = ctx.get("goal", {})
    meta = goal.get("metadata", {}) if isinstance(goal, dict) else {}

    action = meta.get("action", "read")
    channel = meta.get("channel", "default")
    key = meta.get("key", "")
    value = meta.get("value")

    # Ensure blackboard root exists in context
    bb = ctx.setdefault("blackboard", {})
    if not isinstance(bb, dict):
        bb = {}
        ctx["blackboard"] = bb

    if action == "post":
        if not key:
            return {
                "status": "failed",
                "error": "metadata 'key' required for post",
            }
        ch = bb.setdefault(channel, {})
        if not isinstance(ch, dict):
            ch = {}
            bb[channel] = ch
        ch[key] = {
            "value": value,
            "timestamp": __import__("time").time(),
        }
        return {
            "status": "completed",
            "action": "post",
            "channel": channel,
            "key": key,
        }

    elif action == "read":
        if not key:
            return {
                "status": "failed",
                "error": "metadata 'key' required for read",
            }
        ch = bb.get(channel, {})
        if not isinstance(ch, dict):
            return {
                "status": "completed",
                "action": "read",
                "channel": channel,
                "key": key,
                "found": False,
                "value": None,
            }
        entry = ch.get(key)
        return {
            "status": "completed",
            "action": "read",
            "channel": channel,
            "key": key,
            "found": key in ch,
            "value": entry["value"] if entry else None,
            "timestamp": entry.get("timestamp") if entry else None,
        }

    elif action == "list":
        ch = bb.get(channel, {})
        if not isinstance(ch, dict):
            ch = {}
        return {
            "status": "completed",
            "action": "list",
            "channel": channel,
            "keys": list(ch.keys()),
            "count": len(ch),
        }

    return {
        "status": "failed",
        "error": "Unknown action",
    }
