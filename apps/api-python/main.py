from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Literal
import hashlib
import json
import time
import uuid

app = FastAPI(title="Universal Agent Runtime (UAR)", version="0.1.2")

ObjectMode = Literal["immutable", "mutable", "collection"]

STORE: dict[str, dict[str, Any]] = {}
LINEAGE: dict[str, list[dict[str, Any]]] = {}
RUNTIME_REGISTRY: dict[str, str] = {}

AGENTS: dict[str, list[str]] = {
    "locator": ["query"],
    "verifier": ["verify", "compare"],
    "composer": ["compose"],
    "execution": ["run", "run_object", "run_registered"],
    "runtime_registry": ["register", "list", "get", "seed"],
    "lineage": ["trace"],
    "constraint": ["check"],
    "bridge": ["ingest"],
    "inference": ["analyze"],
    "delegation": ["plan"],
}

ALLOWED_BUILTINS = {
    "len": len,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sorted": sorted,
}


def canonical_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def timestamp() -> float:
    return time.time()


def get_obj(digest: str) -> dict[str, Any]:
    if digest not in STORE:
        raise HTTPException(status_code=404, detail=f"Object not found: {digest}")
    return STORE[digest]


def create_record(
    *,
    mediaType: str,
    mode: ObjectMode,
    attributes: dict[str, Any],
    links: list[dict[str, Any]],
    content: Any,
) -> dict[str, Any]:
    envelope = {
        "mediaType": mediaType,
        "mode": mode,
        "schema": attributes.get("schema", "uor.schema.object.v1"),
        "attributes": attributes,
        "links": links,
        "content": content,
    }
    digest = canonical_digest(envelope)
    record = {
        "digest": digest,
        "size": len(json.dumps(envelope, sort_keys=True)),
        "created_at": timestamp(),
        **envelope,
    }
    STORE[digest] = record
    LINEAGE.setdefault(digest, []).append({
        "event": "created",
        "agent": "system",
        "timestamp": timestamp(),
    })
    return record


def extract_runtime_code(runtime_obj: dict[str, Any]) -> str:
    content = runtime_obj.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, dict) and isinstance(content.get("code"), str):
        return content["code"]
    raise HTTPException(
        status_code=400,
        detail="Runtime object content must be a string or an object with a string 'code' field",
    )


def resolve_runtime(runtime_name: str | None, runtime_object: str | None) -> tuple[str, dict[str, Any]]:
    if runtime_name:
        if runtime_name not in RUNTIME_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Runtime not registered: {runtime_name}")
        digest = RUNTIME_REGISTRY[runtime_name]
        return digest, get_obj(digest)
    if runtime_object:
        return runtime_object, get_obj(runtime_object)
    raise HTTPException(status_code=400, detail="Provide runtimeName, runtimeObject, or parameters.code")


def run_code(code: str, input_objects: list[dict[str, Any]], parameters: dict[str, Any]) -> Any:
    local_scope = {
        "inputs": input_objects,
        "parameters": parameters,
        "contents": [obj.get("content") for obj in input_objects],
        "attributes": [obj.get("attributes", {}) for obj in input_objects],
    }
    try:
        return eval(code, {"__builtins__": ALLOWED_BUILTINS}, local_scope)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Execution failed: {exc}") from exc


def register_runtime_object(
    *,
    name: str,
    code: str,
    description: str = "",
    tags: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise HTTPException(status_code=400, detail="Runtime name is required")
    runtime_attributes = {
        "schema": "uar.schema.runtime.v1",
        "type": "runtime",
        "runtimeName": name,
        "description": description,
        "tags": tags or [],
        **(attributes or {}),
    }
    record = create_record(
        mediaType="application/vnd.uar.runtime+json",
        mode="immutable",
        attributes=runtime_attributes,
        links=[],
        content={"code": code},
    )
    RUNTIME_REGISTRY[name] = record["digest"]
    LINEAGE[record["digest"]].append({
        "event": "registered_runtime",
        "agent": "runtime_registry",
        "runtimeName": name,
        "timestamp": timestamp(),
    })
    return record


def seed_standard_runtimes() -> dict[str, str]:
    seeds = {
        "sum_contents": "sum(contents)",
        "count_inputs": "len(inputs)",
        "max_contents": "max(contents)",
        "min_contents": "min(contents)",
        "sort_contents": "sorted(contents)",
    }
    for name, code in seeds.items():
        if name not in RUNTIME_REGISTRY:
            register_runtime_object(
                name=name,
                code=code,
                description=f"Standard runtime: {name}",
                tags=["standard", "math"],
            )
    return RUNTIME_REGISTRY


class UORObjectIn(BaseModel):
    mediaType: str = "application/json"
    mode: ObjectMode = "immutable"
    attributes: dict[str, Any] = Field(default_factory=dict)
    links: list[dict[str, Any]] = Field(default_factory=list)
    content: Any


class RuntimeRegisterReq(BaseModel):
    name: str
    code: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class QueryReq(BaseModel):
    where: dict[str, Any] = Field(default_factory=dict)
    limit: int = 25


class VerifyReq(BaseModel):
    object: str
    expectedDigest: str | None = None


class CompareReq(BaseModel):
    left: str
    right: str


class ComposeReq(BaseModel):
    inputs: list[str]
    compositionType: str = "dataset"
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExecuteReq(BaseModel):
    runtimeName: str | None = None
    runtimeObject: str | None = None
    inputs: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConstraintReq(BaseModel):
    action: str
    agent: str
    target: str
    policy: str | None = None


class BridgeReq(BaseModel):
    source: dict[str, Any]
    normalize: bool = True
    attributes: dict[str, Any] = Field(default_factory=dict)


class InferenceReq(BaseModel):
    objects: list[str]
    task: str
    requireVerification: bool = True


class DelegationReq(BaseModel):
    goal: str
    inputs: list[str] = Field(default_factory=list)
    allowedAgents: list[str] = Field(default_factory=list)


@app.on_event("startup")
def startup_seed_runtimes():
    seed_standard_runtimes()


@app.get("/")
def root():
    return {
        "status": "UAR running",
        "version": "0.1.2",
        "loop": "create -> register-runtime -> execute-by-name -> lineage",
        "registered_runtimes": list(RUNTIME_REGISTRY.keys()),
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "universal-agent-runtime"}


@app.get("/agents")
def list_agents():
    return {
        "agents": [
            {
                "agent_id": f"uar.agent.{name}.v1",
                "name": name,
                "version": "0.1.2",
                "capabilities": capabilities,
            }
            for name, capabilities in AGENTS.items()
        ]
    }


@app.post("/objects")
def create_object(obj: UORObjectIn):
    return create_record(
        mediaType=obj.mediaType,
        mode=obj.mode,
        attributes=obj.attributes,
        links=obj.links,
        content=obj.content,
    )


@app.get("/objects")
def read_object(digest: str = Query(..., description="Object digest, e.g. sha256:<hash>")):
    return get_obj(digest)


@app.post("/runtimes/register")
def register_runtime(req: RuntimeRegisterReq):
    record = register_runtime_object(
        name=req.name,
        code=req.code,
        description=req.description,
        tags=req.tags,
        attributes=req.attributes,
    )
    return {"name": req.name, "runtimeObject": record["digest"], "record": record}


@app.get("/runtimes")
def list_runtimes():
    return {
        "runtimes": [
            {
                "name": name,
                "digest": digest,
                "attributes": get_obj(digest).get("attributes", {}),
            }
            for name, digest in sorted(RUNTIME_REGISTRY.items())
        ]
    }


@app.get("/runtimes/{name}")
def get_runtime(name: str):
    if name not in RUNTIME_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Runtime not registered: {name}")
    digest = RUNTIME_REGISTRY[name]
    return {"name": name, "digest": digest, "record": get_obj(digest)}


@app.post("/runtimes/seed")
def seed_runtimes():
    seed_standard_runtimes()
    return {"seeded": list(RUNTIME_REGISTRY.keys())}


@app.post("/agents/locator/query")
def locator_query(req: QueryReq):
    matches = []
    for digest, obj in STORE.items():
        ok = True
        for key, value in req.where.items():
            cursor: Any = obj
            for part in key.split("."):
                cursor = cursor.get(part) if isinstance(cursor, dict) else None
            if cursor != value:
                ok = False
                break
        if ok:
            matches.append({
                "digest": digest,
                "mediaType": obj.get("mediaType"),
                "mode": obj.get("mode"),
                "attributes": obj.get("attributes", {}),
            })
    return {"matches": matches[: req.limit]}


@app.post("/agents/verifier/verify")
def verifier_verify(req: VerifyReq):
    obj = get_obj(req.object)
    expected = req.expectedDigest or req.object
    verified = obj["digest"] == expected
    return {
        "verified": verified,
        "identity": obj["digest"],
        "method": "sha256",
        "notes": [] if verified else ["digest-mismatch"],
    }


@app.post("/agents/verifier/compare")
def verifier_compare(req: CompareReq):
    left = get_obj(req.left)
    right = get_obj(req.right)
    return {
        "equivalent": left["digest"] == right["digest"],
        "left": left["digest"],
        "right": right["digest"],
    }


@app.post("/agents/composer/compose")
def composer_compose(req: ComposeReq):
    for digest in req.inputs:
        get_obj(digest)
    created = create_record(
        mediaType="application/vnd.uar.dataset+json",
        mode="collection",
        attributes={**req.attributes, "compositionType": req.compositionType},
        links=[{"rel": "contains", "target": digest} for digest in req.inputs],
        content={"items": req.inputs},
    )
    LINEAGE[created["digest"]].append({
        "event": "composed",
        "agent": "composer",
        "inputs": req.inputs,
        "timestamp": timestamp(),
    })
    return {"created": created["digest"], "inputs": req.inputs}


@app.post("/agents/execution/run")
def execution_run(req: ExecuteReq):
    input_objects = [get_obj(digest) for digest in req.inputs]

    if req.runtimeName or req.runtimeObject:
        runtime_digest, runtime_obj = resolve_runtime(req.runtimeName, req.runtimeObject)
        code = extract_runtime_code(runtime_obj)
    elif isinstance(req.parameters.get("code"), str):
        code = req.parameters["code"]
        runtime_digest = None
    else:
        raise HTTPException(status_code=400, detail="Provide runtimeName, runtimeObject, or parameters.code")

    result = run_code(code, input_objects, req.parameters)

    output = create_record(
        mediaType="application/vnd.uar.execution-output+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-output"},
        links=[{"rel": "used", "target": digest} for digest in req.inputs]
        + ([{"rel": "runtime", "target": runtime_digest}] if runtime_digest else []),
        content={"result": result},
    )

    execution_record = create_record(
        mediaType="application/vnd.uar.execution-record+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-record"},
        links=[
            *[{"rel": "input", "target": digest} for digest in req.inputs],
            *([{"rel": "runtime", "target": runtime_digest}] if runtime_digest else []),
            {"rel": "output", "target": output["digest"]},
        ],
        content={
            "execution_id": str(uuid.uuid4()),
            "status": "completed",
            "runtimeName": req.runtimeName,
            "runtimeObject": runtime_digest,
            "parameters": req.parameters,
            "timestamp": timestamp(),
        },
    )

    LINEAGE[output["digest"]].append({
        "event": "executed",
        "agent": "execution",
        "inputs": req.inputs,
        "runtimeName": req.runtimeName,
        "runtimeObject": runtime_digest,
        "executionRecord": execution_record["digest"],
        "timestamp": timestamp(),
    })
    if runtime_digest:
        LINEAGE.setdefault(runtime_digest, []).append({
            "event": "used_as_runtime",
            "agent": "execution",
            "output": output["digest"],
            "executionRecord": execution_record["digest"],
            "timestamp": timestamp(),
        })

    return {
        "status": "completed",
        "output": output["digest"],
        "executionRecord": execution_record["digest"],
        "runtimeName": req.runtimeName,
        "runtimeObject": runtime_digest,
        "result": result,
    }


@app.get("/agents/lineage/trace")
def lineage_trace(digest: str = Query(..., description="Object digest, e.g. sha256:<hash>")):
    get_obj(digest)
    return {"object": digest, "events": LINEAGE.get(digest, [])}


@app.post("/agents/constraint/check")
def constraint_check(req: ConstraintReq):
    get_obj(req.target)
    allowed = req.agent in AGENTS and req.action in AGENTS[req.agent]
    return {
        "allowed": allowed,
        "reason": "capability-authorized" if allowed else "unknown-agent-or-action",
        "violations": [] if allowed else ["capability-not-found"],
    }


@app.post("/agents/bridge/ingest")
def bridge_ingest(req: BridgeReq):
    created = create_record(
        mediaType="application/json",
        mode="immutable",
        attributes={**req.attributes, "source": req.source, "agent": "bridge"},
        links=[],
        content={"normalized": req.normalize, "source": req.source},
    )
    return {"object": created["digest"], "normalizationRecord": created["digest"]}


@app.post("/agents/inference/analyze")
def inference_analyze(req: InferenceReq):
    for digest in req.objects:
        get_obj(digest)
    created = create_record(
        mediaType="application/vnd.uar.analysis+json",
        mode="immutable",
        attributes={"task": req.task, "agent": "inference"},
        links=[{"rel": "analyzed", "target": digest} for digest in req.objects],
        content={"finding_id": str(uuid.uuid4()), "findings": []},
    )
    return {"findings": [], "analysisRecord": created["digest"]}


@app.post("/agents/delegation/plan")
def delegation_plan(req: DelegationReq):
    for digest in req.inputs:
        get_obj(digest)
    allowed = req.allowedAgents or ["verifier", "execution", "lineage"]
    plan = [{"step": i + 1, "agent": agent} for i, agent in enumerate(allowed) if agent in AGENTS]
    created = create_record(
        mediaType="application/vnd.uar.plan+json",
        mode="immutable",
        attributes={"goal": req.goal, "agent": "delegation"},
        links=[{"rel": "input", "target": digest} for digest in req.inputs],
        content={"plan": plan},
    )
    return {"plan": plan, "planObject": created["digest"]}
