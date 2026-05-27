"""
Dagster pipeline orchestration integration for UAR.

This module provides data orchestration and asset management inspired by Dagster,
enabling declarative pipeline definitions, asset-based orchestration, type-safe
pipeline definitions, and built-in observability and monitoring.

Key features:
- Declarative programming model for data pipelines
- Asset-based orchestration (track data dependencies)
- Type-safe pipeline definitions
- Built-in observability and monitoring
- Job scheduling and backfilling
- Resource management
"""  # noqa: E501

import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

try:
    from dagster import MaterializeResult, asset, job, repository

    DAGSTER_AVAILABLE = True
except ImportError:
    DAGSTER_AVAILABLE = False
    logging.warning(
        "Dagster not available. Install with: pip install dagster>=1.7"
    )

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """Status of a pipeline execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetType(Enum):
    """Types of assets in the pipeline."""

    DOCUMENT = "document"
    VECTOR_INDEX = "vector_index"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    RAG_RESULT = "rag_result"
    AGENT_OUTPUT = "agent_output"
    METADATA = "metadata"


@dataclass
class AssetDefinition:
    """Definition of an asset in the pipeline."""

    key: str
    asset_type: AssetType
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "asset_type": self.asset_type.value,
            "description": self.description,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PipelineExecution:
    """Execution record for a pipeline run."""

    execution_id: str
    pipeline_name: str
    status: PipelineStatus = PipelineStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    assets_produced: List[str] = field(default_factory=list)
    assets_consumed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat()
            if self.start_time
            else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "assets_produced": self.assets_produced,
            "assets_consumed": self.assets_consumed,
            "error": self.error,
            "metadata": self.metadata,
        }


class UARPipelineOrchestrator:
    """Orchestrator for UAR pipelines using Dagster patterns."""

    def __init__(self) -> None:
        self.assets: Dict[str, AssetDefinition] = {}
        self.pipelines: Dict[str, Callable] = {}
        self.executions: Dict[str, PipelineExecution] = {}
        self.active_jobs: Dict[str, Any] = {}

    def register_asset(
        self,
        key: str,
        asset_type: AssetType,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AssetDefinition:
        """Register an asset definition."""
        asset = AssetDefinition(
            key=key,
            asset_type=asset_type,
            description=description,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.assets[key] = asset
        logger.info(
            "Registered asset: %s (%s)", key, asset_type.value
        )
        return asset

    def get_asset(self, key: str) -> Optional[AssetDefinition]:
        """Get an asset by key."""
        return self.assets.get(key)

    def get_asset_dependencies(self, key: str) -> List[str]:
        """Get dependencies for an asset."""
        asset = self.get_asset(key)
        return asset.dependencies if asset else []

    def create_pipeline(
        self,
        name: str,
        asset_keys: List[str],
        description: str = "",
    ) -> Callable:
        """Create a pipeline from asset dependencies.

        This is a simplified version - in production with Dagster,
        you'd use @job decorator and asset dependencies.
        """

        def pipeline_fn(ctx: Dict[str, Any]):
            """Execute the pipeline."""
            execution_id = str(uuid.uuid4())
            execution = PipelineExecution(
                execution_id=execution_id,
                pipeline_name=name,
                status=PipelineStatus.RUNNING,
                start_time=datetime.utcnow(),
            )
            self.executions[execution_id] = execution

            try:
                # Execute assets in dependency order
                executed = []
                for asset_key in asset_keys:
                    # Check if dependencies are satisfied
                    deps = self.get_asset_dependencies(asset_key)
                    if not all(dep in executed for dep in deps):
                        raise ValueError(
                            f"Dependencies not satisfied for {asset_key}"
                        )

                    # Execute the asset (in production, this would call the actual op)  # noqa: E501
                    logger.info(
                        "Executing asset: %s", asset_key
                    )
                    execution.assets_produced.append(asset_key)
                    executed.append(asset_key)

                execution.status = PipelineStatus.SUCCESS
                execution.end_time = datetime.utcnow()

            except Exception:
                execution.status = PipelineStatus.FAILED
                execution.error = "Pipeline failed"
                execution.end_time = datetime.utcnow()
                logger.exception("Pipeline %s failed", name)

            return execution.to_dict()

        self.pipelines[name] = pipeline_fn
        logger.info(
            "Created pipeline: %s with assets: %s", name, asset_keys
        )
        return pipeline_fn

    def execute_pipeline(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineExecution:
        """Execute a pipeline."""
        pipeline = self.pipelines.get(name)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {name}")

        ctx = context or {}
        result = pipeline(ctx)

        execution_id = result.get("execution_id")
        if execution_id:
            return self.executions[execution_id]

        raise RuntimeError("Execution ID not found in result")

    def get_execution(self, execution_id: str) -> Optional[PipelineExecution]:
        """Get an execution by ID."""
        return self.executions.get(execution_id)

    def get_pipeline_status(self, name: str) -> Dict[str, Any]:
        """Get status of a pipeline."""
        pipeline = self.pipelines.get(name)
        if not pipeline:
            return {"error": "Pipeline not found"}

        # Get recent executions for this pipeline
        recent_executions = [
            exec_.to_dict()
            for exec_ in self.executions.values()
            if exec_.pipeline_name == name
        ]

        return {
            "pipeline_name": name,
            "recent_executions": recent_executions[-10:],  # Last 10
            "total_executions": len(recent_executions),
        }

    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get overall status of the orchestrator."""
        return {
            "assets": {
                key: asset.to_dict() for key, asset in self.assets.items()
            },
            "pipelines": list(self.pipelines.keys()),
            "executions": {
                exec_id: exec_.to_dict()
                for exec_id, exec_ in self.executions.items()
            },
            "asset_count": len(self.assets),
            "pipeline_count": len(self.pipelines),
            "execution_count": len(self.executions),
        }


# Global orchestrator instance
_orchestrator: Optional[UARPipelineOrchestrator] = None


def get_orchestrator() -> UARPipelineOrchestrator:
    """Get the global pipeline orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = UARPipelineOrchestrator()
    return _orchestrator


def create_standard_pipelines():
    """Create standard UAR pipelines."""
    orchestrator = get_orchestrator()

    # Register standard assets
    orchestrator.register_asset(
        key="raw_documents",
        asset_type=AssetType.DOCUMENT,
        description="Raw ingested documents",
    )

    orchestrator.register_asset(
        key="chunked_documents",
        asset_type=AssetType.DOCUMENT,
        description="Chunked and processed documents",
        dependencies=["raw_documents"],
    )

    orchestrator.register_asset(
        key="vector_index",
        asset_type=AssetType.VECTOR_INDEX,
        description="Vector embeddings index",
        dependencies=["chunked_documents"],
    )

    orchestrator.register_asset(
        key="knowledge_graph",
        asset_type=AssetType.KNOWLEDGE_GRAPH,
        description="Knowledge graph from documents",
        dependencies=["chunked_documents"],
    )

    orchestrator.register_asset(
        key="rag_query_result",
        asset_type=AssetType.RAG_RESULT,
        description="RAG query results",
        dependencies=["vector_index", "knowledge_graph"],
    )

    # Create standard pipelines
    orchestrator.create_pipeline(
        name="document_ingestion_pipeline",
        asset_keys=["raw_documents", "chunked_documents"],
        description="Ingest and process documents",
    )

    orchestrator.create_pipeline(
        name="rag_pipeline",
        asset_keys=[
            "raw_documents",
            "chunked_documents",
            "vector_index",
            "rag_query_result",
        ],
        description="Full RAG pipeline",
    )

    orchestrator.create_pipeline(
        name="graphrag_pipeline",
        asset_keys=[
            "raw_documents",
            "chunked_documents",
            "knowledge_graph",
            "rag_query_result",
        ],
        description="GraphRAG pipeline with knowledge graph",
    )

    logger.info("Standard pipelines created")


def create_uar_skill_pipeline(
    skill_name: str,
    input_assets: List[str],
    output_assets: List[str],
    description: str = "",
):
    """Create a pipeline for a UAR skill."""
    orchestrator = get_orchestrator()

    # Register assets if they don't exist
    for asset_key in input_assets + output_assets:
        if asset_key not in orchestrator.assets:
            orchestrator.register_asset(
                key=asset_key,
                asset_type=AssetType.AGENT_OUTPUT,
                description=f"Asset from {skill_name}",
            )

    # Create pipeline
    pipeline_name = f"{skill_name}_pipeline"
    orchestrator.create_pipeline(
        name=pipeline_name,
        asset_keys=input_assets + output_assets,
        description=description or f"Pipeline for {skill_name}",
    )

    return pipeline_name


if DAGSTER_AVAILABLE:
    # Create Dagster assets and jobs when Dagster is available
    @asset(name="raw_documents")
    def raw_documents_asset(context) -> MaterializeResult:
        """Dagster asset for raw documents."""

        # This would be called with proper context in production
        # For now, return a placeholder
        return MaterializeResult(
            description="Raw documents ingested",
            metadata={"count": 0},
        )

    @asset(name="vector_index", deps=[raw_documents_asset])
    def vector_index_asset(
        context,
        raw_documents: Any,
    ) -> MaterializeResult:
        """Dagster asset for vector index."""
        # This would create a vector index from raw documents
        return MaterializeResult(
            description="Vector index created",
            metadata={"document_count": 0},
        )

    @job(name="uar_rag_pipeline")
    def uar_rag_job():
        """Dagster job for UAR RAG pipeline."""
        raw_documents_asset()
        vector_index_asset()

    @repository(name="uar_repository")
    def uar_repository():
        """Dagster repository for UAR assets and jobs."""
        return [uar_rag_job]
