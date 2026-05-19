"""High-level UOR service operations used by the FastAPI routers.

These helpers operate on an :class:`uar.objects.store.ObjectStore`
instance and orchestrate the lower-level digest/sandbox primitives.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .agents import AGENTS
from .sandbox import SandboxError, run_code, validate_code
from .store import ObjectStore

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Digest helpers
# ----------------------------------------------------------------------
def canonical_digest(payload: Any) -> str:
    """SHA-256 of canonical-JSON of ``payload``."""
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _timestamp() -> float:
    return time.time()


# ----------------------------------------------------------------------
# Object record helpers
# ----------------------------------------------------------------------
def add_lineage(
    store: ObjectStore, digest: str, event: Dict[str, Any]
) -> None:
    store.append_lineage(digest, event)


def create_record(
    store: ObjectStore,
    *,
    mediaType: str,
    mode: str,
    attributes: Dict[str, Any],
    links: List[Dict[str, Any]],
    content: Any,
) -> Dict[str, Any]:
    """Persist an immutable UOR record and emit a ``created`` lineage event."""
    envelope = {
        "mediaType": mediaType,
        "mode": mode,
        "schema": attributes.get("schema", "uor.schema.object.v1"),
        "attributes": attributes,
        "links": links,
        "content": content,
    }
    digest = canonical_digest(envelope)
    record: Dict[str, Any] = {
        "digest": digest,
        "size": len(json.dumps(envelope, sort_keys=True)),
        "created_at": _timestamp(),
        **envelope,
    }
    store.put_object(record)
    add_lineage(
        store,
        digest,
        {
            "event": "created",
            "agent": "system",
            "timestamp": _timestamp(),
        },
    )
    return record


def object_value(obj: Dict[str, Any]) -> Any:
    """Unwrap ``content`` shape ``{"result": x}`` to ``x`` for chaining."""
    content = obj.get("content")
    if isinstance(content, dict) and set(content.keys()) == {"result"}:
        return content["result"]
    return content


# ----------------------------------------------------------------------
# Runtime helpers
# ----------------------------------------------------------------------
def extract_runtime_code(runtime_obj: Dict[str, Any]) -> str:
    content = runtime_obj.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, dict) and isinstance(content.get("code"), str):
        return content["code"]
    raise SandboxError(
        "Runtime object content must be a string or "
        "an object with a string 'code' field"
    )


def resolve_runtime(
    store: ObjectStore,
    runtime_name: Optional[str],
    runtime_object: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    if runtime_name:
        digest = store.get_runtime_digest(runtime_name)
        if digest is None:
            raise KeyError(f"Runtime not registered: {runtime_name}")
        return digest, store.get_object(digest)
    if runtime_object:
        return runtime_object, store.get_object(runtime_object)
    raise SandboxError(
        "Provide runtimeName, runtimeObject, or parameters.code"
    )


def register_runtime_object(
    store: ObjectStore,
    *,
    name: str,
    code: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    attributes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not name.strip():
        raise SandboxError("Runtime name is required")
    validate_code(code)
    runtime_attributes = {
        "schema": "uar.schema.runtime.v1",
        "type": "runtime",
        "runtimeName": name,
        "description": description,
        "tags": list(tags or []),
        **(attributes or {}),
    }
    record = create_record(
        store,
        mediaType="application/vnd.uar.runtime+json",
        mode="immutable",
        attributes=runtime_attributes,
        links=[],
        content={"code": code},
    )
    store.register_runtime(name, record["digest"])
    add_lineage(
        store,
        record["digest"],
        {
            "event": "registered_runtime",
            "agent": "runtime_registry",
            "runtimeName": name,
            "timestamp": _timestamp(),
        },
    )
    return record


STANDARD_RUNTIMES: Dict[str, str] = {
    "sum_contents": "sum(values)",
    "count_inputs": "len(inputs)",
    "max_contents": "max(values)",
    "min_contents": "min(values)",
    "sort_contents": "sorted(values)",
    "identity_value": "values[0]",
}


def seed_standard_runtimes(store: ObjectStore) -> Dict[str, str]:
    """Register the canonical math runtimes if not already present."""
    for name, code in STANDARD_RUNTIMES.items():
        if store.get_runtime_digest(name) is None:
            register_runtime_object(
                store,
                name=name,
                code=code,
                description=f"Standard runtime: {name}",
                tags=["standard", "math"],
            )
    return store.list_runtimes()


# ----------------------------------------------------------------------
# Execution
# ----------------------------------------------------------------------
def execute_runtime(
    store: ObjectStore,
    *,
    runtime_name: Optional[str],
    runtime_object: Optional[str],
    inputs: List[str],
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    input_objects = [store.get_object(digest) for digest in inputs]

    if runtime_name or runtime_object:
        runtime_digest, runtime_obj = resolve_runtime(
            store, runtime_name, runtime_object
        )
        code = extract_runtime_code(runtime_obj)
    elif isinstance(parameters.get("code"), str):
        code = parameters["code"]
        runtime_digest = None
    else:
        raise SandboxError(
            "Provide runtimeName, runtimeObject, or parameters.code"
        )

    result = run_code(code, input_objects, parameters)

    output = create_record(
        store,
        mediaType="application/vnd.uar.execution-output+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-output"},
        links=[{"rel": "used", "target": digest} for digest in inputs]
        + (
            [{"rel": "runtime", "target": runtime_digest}]
            if runtime_digest
            else []
        ),
        content={"result": result},
    )
    execution_record = create_record(
        store,
        mediaType="application/vnd.uar.execution-record+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-record"},
        links=[
            *[{"rel": "input", "target": digest} for digest in inputs],
            *(
                [{"rel": "runtime", "target": runtime_digest}]
                if runtime_digest
                else []
            ),
            {"rel": "output", "target": output["digest"]},
        ],
        content={
            "execution_id": str(uuid.uuid4()),
            "status": "completed",
            "runtimeName": runtime_name,
            "runtimeObject": runtime_digest,
            "parameters": parameters,
            "timestamp": _timestamp(),
        },
    )

    add_lineage(
        store,
        output["digest"],
        {
            "event": "executed",
            "agent": "execution",
            "inputs": inputs,
            "runtimeName": runtime_name,
            "runtimeObject": runtime_digest,
            "executionRecord": execution_record["digest"],
            "timestamp": _timestamp(),
        },
    )
    if runtime_digest:
        add_lineage(
            store,
            runtime_digest,
            {
                "event": "used_as_runtime",
                "agent": "execution",
                "output": output["digest"],
                "executionRecord": execution_record["digest"],
                "timestamp": _timestamp(),
            },
        )
    return {
        "status": "completed",
        "output": output["digest"],
        "executionRecord": execution_record["digest"],
        "runtimeName": runtime_name,
        "runtimeObject": runtime_digest,
        "result": result,
    }


# ----------------------------------------------------------------------
# Workflow
# ----------------------------------------------------------------------
def workflow_run(
    store: ObjectStore,
    *,
    name: str,
    inputs: List[str],
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not steps:
        raise SandboxError("Workflow requires at least one step")
    current_inputs = list(inputs)
    step_results: List[Dict[str, Any]] = []
    workflow_id = str(uuid.uuid4())

    for index, step in enumerate(steps, start=1):
        use_previous = bool(step.get("usePreviousOutput", True))
        step_inputs = (
            current_inputs
            if use_previous or index == 1
            else list(inputs)
        )
        result = execute_runtime(
            store,
            runtime_name=step.get("runtimeName"),
            runtime_object=step.get("runtimeObject"),
            inputs=step_inputs,
            parameters={
                **step.get("parameters", {}),
                "workflow_id": workflow_id,
                "step": index,
            },
        )
        step_results.append({"step": index, **result})
        current_inputs = [result["output"]]

    workflow_record = create_record(
        store,
        mediaType="application/vnd.uar.workflow-record+json",
        mode="immutable",
        attributes={
            "agent": "workflow",
            "kind": "workflow-record",
            "workflowName": name,
        },
        links=[
            *[
                {"rel": "initial_input", "target": digest}
                for digest in inputs
            ],
            *[
                {"rel": "step_output", "target": item["output"]}
                for item in step_results
            ],
        ],
        content={
            "workflow_id": workflow_id,
            "name": name,
            "steps": step_results,
            "final_output": step_results[-1]["output"],
            "timestamp": _timestamp(),
        },
    )
    add_lineage(
        store,
        workflow_record["digest"],
        {
            "event": "workflow_completed",
            "agent": "workflow",
            "workflow_id": workflow_id,
            "final_output": step_results[-1]["output"],
            "timestamp": _timestamp(),
        },
    )
    return {
        "status": "completed",
        "workflowRecord": workflow_record["digest"],
        "finalOutput": step_results[-1]["output"],
        "steps": step_results,
    }


# ----------------------------------------------------------------------
# Locator / inference / delegation / bridge / constraint
# ----------------------------------------------------------------------
def locator_query(
    store: ObjectStore, where: Dict[str, Any], limit: int
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for digest, obj in store.iter_objects():
        ok = True
        for key, value in where.items():
            cursor: Any = obj
            for part in key.split("."):
                cursor = (
                    cursor.get(part) if isinstance(cursor, dict) else None
                )
            if cursor != value:
                ok = False
                break
        if ok:
            matches.append(
                {
                    "digest": digest,
                    "mediaType": obj.get("mediaType"),
                    "mode": obj.get("mode"),
                    "attributes": obj.get("attributes", {}),
                }
            )
    return matches[:limit]


def constraint_check(
    store: ObjectStore, *, agent: str, action: str, target: str
) -> Dict[str, Any]:
    store.get_object(target)  # raises KeyError if missing
    allowed = agent in AGENTS and action in AGENTS[agent]
    return {
        "allowed": allowed,
        "reason": (
            "capability-authorized"
            if allowed
            else "unknown-agent-or-action"
        ),
        "violations": [] if allowed else ["capability-not-found"],
    }


def bridge_ingest(
    store: ObjectStore,
    *,
    source: Dict[str, Any],
    normalize: bool,
    attributes: Dict[str, Any],
) -> Dict[str, Any]:
    created = create_record(
        store,
        mediaType="application/json",
        mode="immutable",
        attributes={**attributes, "source": source, "agent": "bridge"},
        links=[],
        content={"normalized": normalize, "source": source},
    )
    return {
        "object": created["digest"],
        "normalizationRecord": created["digest"],
    }


def inference_analyze(
    store: ObjectStore, *, objects: List[str], task: str
) -> Dict[str, Any]:
    for digest in objects:
        store.get_object(digest)
    created = create_record(
        store,
        mediaType="application/vnd.uar.analysis+json",
        mode="immutable",
        attributes={"task": task, "agent": "inference"},
        links=[
            {"rel": "analyzed", "target": digest} for digest in objects
        ],
        content={"finding_id": str(uuid.uuid4()), "findings": []},
    )
    return {"findings": [], "analysisRecord": created["digest"]}


def delegation_plan(
    store: ObjectStore,
    *,
    goal: str,
    inputs: List[str],
    allowed_agents: List[str],
) -> Dict[str, Any]:
    for digest in inputs:
        store.get_object(digest)
    allowed = allowed_agents or ["verifier", "execution", "lineage"]
    plan = [
        {"step": i + 1, "agent": agent}
        for i, agent in enumerate(allowed)
        if agent in AGENTS
    ]
    created = create_record(
        store,
        mediaType="application/vnd.uar.plan+json",
        mode="immutable",
        attributes={"goal": goal, "agent": "delegation"},
        links=[{"rel": "input", "target": digest} for digest in inputs],
        content={"plan": plan},
    )
    return {"plan": plan, "planObject": created["digest"]}


__all__ = [
    "STANDARD_RUNTIMES",
    "add_lineage",
    "bridge_ingest",
    "canonical_digest",
    "constraint_check",
    "create_record",
    "delegation_plan",
    "execute_runtime",
    "extract_runtime_code",
    "inference_analyze",
    "locator_query",
    "object_value",
    "register_runtime_object",
    "resolve_runtime",
    "seed_standard_runtimes",
    "workflow_run",
]
