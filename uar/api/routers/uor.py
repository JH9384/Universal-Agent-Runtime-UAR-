"""UOR object/runtime/agent endpoints, consolidated into the main UAR app.

These endpoints provide UOR Foundation conformance: content-addressed
objects (``/objects``), lineage tracing (``/agents/lineage/trace``),
sandboxed runtime registration and execution (``/runtimes/*``,
``/agents/execution/*``), and the supporting agent-style verbs
(``/agents/locator/query``, ``/agents/verifier/*``, ``/agents/composer/*``,
``/agents/workflow/*``, ``/agents/constraint/*``, ``/agents/bridge/*``,
``/agents/inference/*``, ``/agents/delegation/*``,
``/agents/atomic_lang_model/*``).

The router uses a per-request :class:`uar.objects.store.ObjectStore`
dependency so tests can override it via FastAPI's dependency-overrides
machinery.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
)

from uar.objects import (
    AGENTS,
    BridgeReq,
    CompareReq,
    ComposeReq,
    ConstraintReq,
    DelegationReq,
    ExecuteReq,
    InferenceReq,
    ObjectStore,
    QueryReq,
    RuntimeRegisterReq,
    SandboxError,
    UORObjectIn,
    VerifyReq,
    WorkflowRunReq,
    create_record,
    execute_runtime,
    get_default_store,
    register_runtime_object,
    workflow_run,
)
from uar.objects.alm_client import AtomicLanguageModelSkill
from uar.objects.models import (
    AtomicLangModelAnalyzeReq,
    AtomicLangModelGenerateReq,
    AtomicLangModelVerifyReq,
)
from uar.objects.service import (
    add_lineage,
    bridge_ingest as svc_bridge_ingest,
    constraint_check as svc_constraint_check,
    delegation_plan as svc_delegation_plan,
    inference_analyze as svc_inference_analyze,
    locator_query as svc_locator_query,
)

logger = logging.getLogger(__name__)


def get_store() -> ObjectStore:
    """Default dependency. Tests override via ``app.dependency_overrides``."""
    return get_default_store()


router = APIRouter(tags=["uor"])


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _require_object(store: ObjectStore, digest: str) -> Dict[str, Any]:
    try:
        return store.get_object(digest)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Object not found"
        ) from exc


# ----------------------------------------------------------------------
# Object endpoints
# ----------------------------------------------------------------------
@router.post("/objects")
def post_object(
    obj: UORObjectIn, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    return create_record(
        store,
        mediaType=obj.mediaType,
        mode=obj.mode,
        attributes=obj.attributes,
        links=obj.links,
        content=obj.content,
    )


@router.get("/objects")
def get_object(
    digest: str = Query(..., description="Object digest, e.g. sha256:<hash>"),
    store: ObjectStore = Depends(get_store),
) -> Dict[str, Any]:
    return _require_object(store, digest)


@router.post("/objects/{digest}/content")
def post_object_content(
    digest: str,
    file: UploadFile,
    store: ObjectStore = Depends(get_store),
) -> Dict[str, Any]:
    """Upload binary content for an existing UOR object."""
    _require_object(store, digest)
    content = file.file.read()
    store.store_content(digest, file.content_type or "application/octet-stream", content)  # noqa: E501
    return {
        "digest": digest,
        "media_type": file.content_type or "application/octet-stream",
        "size": len(content),
    }


@router.get("/objects/{digest}/download")
def get_object_download(
    digest: str,
    store: ObjectStore = Depends(get_store),
) -> Response:
    """Download binary content keyed by object digest."""
    _require_object(store, digest)
    blob = store.get_content(digest)
    if blob is None:
        raise HTTPException(
            status_code=404, detail="No content for object"
        )
    return Response(
        content=blob["content_bytes"],
        media_type=blob["media_type"],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{digest.replace(":", "_")}"'
            ),
        },
    )


# ----------------------------------------------------------------------
# Runtime registry
# ----------------------------------------------------------------------
@router.post("/runtimes/register")
def post_runtimes_register(
    req: RuntimeRegisterReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    try:
        record = register_runtime_object(
            store,
            name=req.name,
            code=req.code,
            description=req.description,
            tags=req.tags,
            attributes=req.attributes,
        )
    except SandboxError as exc:
        raise HTTPException(
            status_code=400, detail="Sandbox validation failed"
        ) from exc
    return {
        "name": req.name,
        "runtimeObject": record["digest"],
        "record": record,
    }


@router.get("/runtimes")
def get_runtimes(
    store: ObjectStore = Depends(get_store),
) -> Dict[str, Any]:
    return {
        "runtimes": [
            {
                "name": name,
                "digest": digest,
                "attributes": store.get_object(digest).get("attributes", {}),
            }
            for name, digest in sorted(store.list_runtimes().items())
        ]
    }


@router.get("/runtimes/{name}")
def get_runtime(
    name: str, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    digest = store.get_runtime_digest(name)
    if digest is None:
        raise HTTPException(
            status_code=404, detail="Runtime not registered"
        )
    return {
        "name": name,
        "digest": digest,
        "record": _require_object(store, digest),
    }


@router.post("/runtimes/seed")
def post_runtimes_seed(
    store: ObjectStore = Depends(get_store),
) -> Dict[str, Any]:
    from uar.objects import seed_standard_runtimes

    seeded = seed_standard_runtimes(store)
    return {"seeded": list(seeded.keys())}


# ----------------------------------------------------------------------
# Agents - listing
# ----------------------------------------------------------------------
@router.get("/agents")
def list_agents() -> Dict[str, Any]:
    return {
        "agents": [
            {
                "agent_id": f"uar.agent.{name}.v1",
                "name": name,
                "version": "1.0.0",
                "capabilities": capabilities,
            }
            for name, capabilities in AGENTS.items()
        ]
    }


# ----------------------------------------------------------------------
# Agents - locator / verifier / composer
# ----------------------------------------------------------------------
@router.post("/agents/locator/query")
def post_locator_query(
    req: QueryReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    matches = svc_locator_query(store, req.where, req.limit)
    return {"matches": matches}


@router.post("/agents/verifier/verify")
def post_verifier_verify(
    req: VerifyReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    obj = _require_object(store, req.object)
    expected = req.expectedDigest or req.object
    verified = obj["digest"] == expected
    return {
        "verified": verified,
        "identity": obj["digest"],
        "method": "sha256",
        "notes": [] if verified else ["digest-mismatch"],
    }


@router.post("/agents/verifier/compare")
def post_verifier_compare(
    req: CompareReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    left = _require_object(store, req.left)
    right = _require_object(store, req.right)
    return {
        "equivalent": left["digest"] == right["digest"],
        "left": left["digest"],
        "right": right["digest"],
    }


@router.post("/agents/composer/compose")
def post_composer_compose(
    req: ComposeReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    for digest in req.inputs:
        _require_object(store, digest)
    created = create_record(
        store,
        mediaType="application/vnd.uar.dataset+json",
        mode="collection",
        attributes={
            **req.attributes,
            "compositionType": req.compositionType,
        },
        links=[{"rel": "contains", "target": digest} for digest in req.inputs],
        content={"items": req.inputs},
    )
    add_lineage(
        store,
        created["digest"],
        {
            "event": "composed",
            "agent": "composer",
            "inputs": req.inputs,
            "timestamp": created["created_at"],
        },
    )
    return {"created": created["digest"], "inputs": req.inputs}


# ----------------------------------------------------------------------
# Agents - execution / workflow
# ----------------------------------------------------------------------
@router.post("/agents/execution/run")
def post_execution_run(
    req: ExecuteReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    try:
        return execute_runtime(
            store,
            runtime_name=req.runtimeName,
            runtime_object=req.runtimeObject,
            inputs=req.inputs,
            parameters=req.parameters,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found") from None
    except SandboxError as exc:
        msg = str(exc)
        status_code = 408 if "timed out" in msg.lower() else 400
        raise HTTPException(
            status_code=status_code, detail="Execution failed"
        ) from exc


@router.post("/agents/workflow/run")
def post_workflow_run_agent(
    req: WorkflowRunReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    return _run_workflow(req, store)


@router.post("/workflows/run")
def post_workflows_run(
    req: WorkflowRunReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    return _run_workflow(req, store)


def _run_workflow(req: WorkflowRunReq, store: ObjectStore) -> Dict[str, Any]:
    try:
        return workflow_run(
            store,
            name=req.name,
            inputs=req.inputs,
            steps=[step.model_dump() for step in req.steps],
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found") from None
    except SandboxError as exc:
        msg = str(exc)
        status_code = 408 if "timed out" in msg.lower() else 400
        raise HTTPException(
            status_code=status_code, detail="Execution failed"
        ) from exc


# ----------------------------------------------------------------------
# Agents - lineage / constraint / bridge / inference / delegation
# ----------------------------------------------------------------------
@router.get("/agents/lineage/trace")
def get_lineage_trace(
    digest: str = Query(..., description="Object digest, e.g. sha256:<hash>"),
    store: ObjectStore = Depends(get_store),
) -> Dict[str, Any]:
    _require_object(store, digest)
    return {"object": digest, "events": store.get_lineage(digest)}


@router.post("/agents/constraint/check")
def post_constraint_check(
    req: ConstraintReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    try:
        return svc_constraint_check(
            store, agent=req.agent, action=req.action, target=req.target
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Object not found"
        ) from exc


@router.post("/agents/bridge/ingest")
def post_bridge_ingest(
    req: BridgeReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    return svc_bridge_ingest(
        store,
        source=req.source,
        normalize=req.normalize,
        attributes=req.attributes,
    )


@router.post("/agents/inference/analyze")
def post_inference_analyze(
    req: InferenceReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    try:
        return svc_inference_analyze(store, objects=req.objects, task=req.task)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Object not found"
        ) from exc


@router.post("/agents/delegation/plan")
def post_delegation_plan(
    req: DelegationReq, store: ObjectStore = Depends(get_store)
) -> Dict[str, Any]:
    try:
        return svc_delegation_plan(
            store,
            goal=req.goal,
            inputs=req.inputs,
            allowed_agents=req.allowedAgents,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Object not found"
        ) from exc


# ----------------------------------------------------------------------
# Agents - atomic language model (HTTP client)
# ----------------------------------------------------------------------
@router.post("/agents/atomic_lang_model/analyze")
def post_alm_analyze(req: AtomicLangModelAnalyzeReq) -> Dict[str, Any]:
    skill = AtomicLanguageModelSkill()
    return skill.analyze_grammar(req.grammar_spec)


@router.post("/agents/atomic_lang_model/generate")
def post_alm_generate(
    req: AtomicLangModelGenerateReq,
) -> Dict[str, Any]:
    skill = AtomicLanguageModelSkill()
    generated: List[str] = skill.generate_sequence(req.prefix, req.count)
    return {
        "generated": generated,
        "prefix": req.prefix,
        "count": req.count,
    }


@router.post("/agents/atomic_lang_model/verify")
def post_alm_verify(req: AtomicLangModelVerifyReq) -> Dict[str, Any]:
    skill = AtomicLanguageModelSkill()
    return skill.verify_syntax(req.text)


# ----------------------------------------------------------------------
# UOR Ecosystem status
# ----------------------------------------------------------------------
@router.get("/ecosystem/status")
def get_ecosystem_status() -> Dict[str, Any]:
    from uar.core.uor_ecosystem import get_uor_ecosystem

    eco = get_uor_ecosystem()
    return {"status": "ok", "integrations": eco.status()}


__all__ = ["router", "get_store"]
