"""UOR-conformant object/runtime/agent persistence layer.

This package consolidates what was previously a separate FastAPI app at
``apps/api-python/`` into the canonical UAR runtime. It exposes:

- :class:`ObjectStore` — thread-safe SQLite-backed store for UOR objects,
  lineage events, and runtime registry entries.
- :class:`Sandbox` — AST-validated subprocess execution for registered
  runtime "code objects".
- :data:`AGENTS` — capability map enforced by the constraint endpoint.
- High-level service helpers (:func:`create_record`,
  :func:`register_runtime_object`, :func:`execute_runtime`,
  :func:`workflow_run`) used by the FastAPI routers in
  :mod:`uar.api.routers`.
- PSERA evidence emission and read-only evidence graph projections.

Configuration is provided by :mod:`uar.objects.settings` (env-driven via
``pydantic-settings`` if available, otherwise plain env reads).
"""

from .agents import AGENTS
from .evidence import EVIDENCE_SCHEMA, emit_evidence, emit_execution_evidence
from .evidence_graph import (
    is_evidence_record,
    iter_evidence,
    mission_control_evidence_projection,
    project_evidence_graph,
)
from .models import (
    BridgeReq,
    CompareReq,
    ComposeReq,
    ConstraintReq,
    DelegationReq,
    ExecuteReq,
    InferenceReq,
    QueryReq,
    RuntimeRegisterReq,
    UORObjectIn,
    VerifyReq,
    WorkflowRunReq,
    WorkflowStep,
)
from .sandbox import (
    DEFAULT_MEMORY_MB,
    DEFAULT_TIMEOUT_SECONDS,
    SandboxError,
    run_code,
    validate_code,
)
from .service import (
    add_lineage,
    canonical_digest,
    create_record,
    execute_runtime,
    register_runtime_object,
    seed_standard_runtimes,
    workflow_run,
)
from .store import ObjectStore, get_default_store

__all__ = [
    "AGENTS",
    "BridgeReq",
    "CompareReq",
    "ComposeReq",
    "ConstraintReq",
    "DEFAULT_MEMORY_MB",
    "DEFAULT_TIMEOUT_SECONDS",
    "DelegationReq",
    "EVIDENCE_SCHEMA",
    "ExecuteReq",
    "InferenceReq",
    "ObjectStore",
    "QueryReq",
    "RuntimeRegisterReq",
    "SandboxError",
    "UORObjectIn",
    "VerifyReq",
    "WorkflowRunReq",
    "WorkflowStep",
    "add_lineage",
    "canonical_digest",
    "create_record",
    "emit_evidence",
    "emit_execution_evidence",
    "execute_runtime",
    "get_default_store",
    "is_evidence_record",
    "iter_evidence",
    "mission_control_evidence_projection",
    "project_evidence_graph",
    "register_runtime_object",
    "run_code",
    "seed_standard_runtimes",
    "validate_code",
    "workflow_run",
]
