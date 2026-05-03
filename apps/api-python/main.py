from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Literal
import ast
import hashlib
import json
import multiprocessing as mp

import multiprocessing as mp
from typing import Any

# Use an explicit "fork" context for child execution so worker processes
# inherit the parent interpreter state (including ad-hoc test-loaded modules).
# The default on macOS is "spawn", which re-imports this module by name and
# fails when the test fixture loads it under a synthesized name.
try:
    _MP_CTX: Any = mp.get_context("fork")
except ValueError:  # pragma: no cover - platforms without fork
    _MP_CTX = mp.get_context()
import queue
import resource
import sqlite3
import time
import uuid

app = FastAPI(title="Universal Agent Runtime (UAR)", version="0.2.2")

DB_PATH = "uar.sqlite3"
DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_MEMORY_MB = 128
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
    "workflow": ["run"],
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
ALLOWED_NAMES = {
    "inputs",
    "parameters",
    "contents",
    "values",
    "attributes",
    *ALLOWED_BUILTINS.keys(),
}
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Subscript,
    ast.Slice,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS objects (digest TEXT PRIMARY KEY, record_json TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS lineage (digest TEXT NOT NULL, event_json TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS runtime_registry (name TEXT PRIMARY KEY, digest TEXT NOT NULL)")
        conn.commit()


def load_db() -> None:
    STORE.clear()
    LINEAGE.clear()
    RUNTIME_REGISTRY.clear()
    with db() as conn:
        for row in conn.execute("SELECT digest, record_json FROM objects"):
            STORE[row["digest"]] = json.loads(row["record_json"])
        for row in conn.execute("SELECT digest, event_json FROM lineage"):
            LINEAGE.setdefault(row["digest"], []).append(json.loads(row["event_json"]))
        for row in conn.execute("SELECT name, digest FROM runtime_registry"):
            RUNTIME_REGISTRY[row["name"]] = row["digest"]


def persist_object(record: dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO objects (digest, record_json) VALUES (?, ?)",
            (record["digest"], json.dumps(record, sort_keys=True)),
        )
        conn.commit()


def persist_lineage(digest: str, event: dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO lineage (digest, event_json) VALUES (?, ?)",
            (digest, json.dumps(event, sort_keys=True)),
        )
        conn.commit()


def persist_runtime(name: str, digest: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runtime_registry (name, digest) VALUES (?, ?)",
            (name, digest),
        )
        conn.commit()


def add_lineage(digest: str, event: dict[str, Any]) -> None:
    LINEAGE.setdefault(digest, []).append(event)
    persist_lineage(digest, event)


def canonical_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def timestamp() -> float:
    return time.time()


def get_obj(digest: str) -> dict[str, Any]:
    if digest not in STORE:
        raise HTTPException(status_code=404, detail=f"Object not found: {digest}")
    return STORE[digest]


def object_value(obj: dict[str, Any]) -> Any:
    content = obj.get("content")
    if isinstance(content, dict) and set(content.keys()) == {"result"}:
        return content["result"]
    return content


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
    persist_object(record)
    add_lineage(digest, {"event": "created", "agent": "system", "timestamp": timestamp()})
    return record


def validate_code(code: str) -> None:
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid runtime syntax: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise HTTPException(status_code=400, detail=f"Disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES:
            raise HTTPException(status_code=400, detail=f"Disallowed name: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_BUILTINS:
                raise HTTPException(status_code=400, detail="Only approved builtin calls are allowed")


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


def _safe_child_exec(
    code: str,
    input_objects: list[dict[str, Any]],
    parameters: dict[str, Any],
    memory_mb: int,
    result_queue: mp.Queue,
) -> None:
    try:
        if hasattr(resource, "setrlimit"):
            memory_bytes = int(memory_mb) * 1024 * 1024
            # Best-effort rlimit application. macOS and some sandboxes reject
            # these values ("current limit exceeds maximum limit"); those
            # failures must not break execution, they only relax sandboxing.
            for _res, _vals in (
                (resource.RLIMIT_AS, (memory_bytes, memory_bytes)),
                (resource.RLIMIT_CPU, (2, 2)),
            ):
                try:
                    resource.setrlimit(_res, _vals)
                except (ValueError, OSError):
                    pass
        local_scope = {
            "inputs": input_objects,
            "parameters": parameters,
            "contents": [obj.get("content") for obj in input_objects],
            "values": [object_value(obj) for obj in input_objects],
            "attributes": [obj.get("attributes", {}) for obj in input_objects],
        }
        result = eval(code, {"__builtins__": ALLOWED_BUILTINS}, local_scope)
        result_queue.put({"ok": True, "result": result})
    except BaseException as exc:  # child process should never leak exceptions outward
        result_queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_code(code: str, input_objects: list[dict[str, Any]], parameters: dict[str, Any]) -> Any:
    validate_code(code)
    timeout_seconds = float(parameters.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    memory_mb = int(parameters.get("memory_mb", DEFAULT_MEMORY_MB))
    timeout_seconds = max(0.1, min(timeout_seconds, 10.0))
    memory_mb = max(32, min(memory_mb, 512))

    result_queue: mp.Queue = _MP_CTX.Queue(maxsize=1)
    process = _MP_CTX.Process(
        target=_safe_child_exec,
        args=(code, input_objects, parameters, memory_mb, result_queue),
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(0.5)
        raise HTTPException(status_code=408, detail="Execution timed out")

    try:
        payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise HTTPException(status_code=400, detail="Execution failed without result") from exc

    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=f"Execution failed: {payload.get('error')}")
    return payload.get("result")


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
    validate_code(code)
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
    persist_runtime(name, record["digest"])
    add_lineage(record["digest"], {
        "event": "registered_runtime",
        "agent": "runtime_registry",
        "runtimeName": name,
        "timestamp": timestamp(),
    })
    return record


def seed_standard_runtimes() -> dict[str, str]:
    seeds = {
        "sum_contents": "sum(values)",
        "count_inputs": "len(inputs)",
        "max_contents": "max(values)",
        "min_contents": "min(values)",
        "sort_contents": "sorted(values)",
        "identity_value": "values[0]",
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


def execute_runtime(
    *,
    runtime_name: str | None,
    runtime_object: str | None,
    inputs: list[str],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    input_objects = [get_obj(digest) for digest in inputs]

    if runtime_name or runtime_object:
        runtime_digest, runtime_obj = resolve_runtime(runtime_name, runtime_object)
        code = extract_runtime_code(runtime_obj)
    elif isinstance(parameters.get("code"), str):
        code = parameters["code"]
        runtime_digest = None
    else:
        raise HTTPException(status_code=400, detail="Provide runtimeName, runtimeObject, or parameters.code")

    result = run_code(code, input_objects, parameters)
    output = create_record(
        mediaType="application/vnd.uar.execution-output+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-output"},
        links=[{"rel": "used", "target": digest} for digest in inputs]
        + ([{"rel": "runtime", "target": runtime_digest}] if runtime_digest else []),
        content={"result": result},
    )
    execution_record = create_record(
        mediaType="application/vnd.uar.execution-record+json",
        mode="immutable",
        attributes={"agent": "execution", "kind": "execution-record"},
        links=[
            *[{"rel": "input", "target": digest} for digest in inputs],
            *([{"rel": "runtime", "target": runtime_digest}] if runtime_digest else []),
            {"rel": "output", "target": output["digest"]},
        ],
        content={
            "execution_id": str(uuid.uuid4()),
            "status": "completed",
            "runtimeName": runtime_name,
            "runtimeObject": runtime_digest,
            "parameters": parameters,
            "timestamp": timestamp(),
        },
    )
    add_lineage(output["digest"], {
        "event": "executed",
        "agent": "execution",
        "inputs": inputs,
        "runtimeName": runtime_name,
        "runtimeObject": runtime_digest,
        "executionRecord": execution_record["digest"],
        "timestamp": timestamp(),
    })
    if runtime_digest:
        add_lineage(runtime_digest, {
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
        "runtimeName": runtime_name,
        "runtimeObject": runtime_digest,
        "result": result,
    }


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


class WorkflowStep(BaseModel):
    runtimeName: str | None = None
    runtimeObject: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    usePreviousOutput: bool = True


class WorkflowRunReq(BaseModel):
    name: str = "adhoc-workflow"
    inputs: list[str] = Field(default_factory=list)
    steps: list[WorkflowStep]


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
def startup_init():
    init_db()
    load_db()
    seed_standard_runtimes()


@app.get("/")
def root():
    return {
        "status": "UAR running",
        "version": "0.2.2",
        "loop": "create -> register-runtime -> sandboxed-execution -> workflow-chain -> persistence",
        "registered_runtimes": list(RUNTIME_REGISTRY.keys()),
        "object_count": len(STORE),
        "sandbox": {
            "mode": "subprocess",
            "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "default_memory_mb": DEFAULT_MEMORY_MB,
        },
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "universal-agent-runtime", "db": DB_PATH}


@app.get("/agents")
def list_agents():
    return {
        "agents": [
            {
                "agent_id": f"uar.agent.{name}.v1",
                "name": name,
                "version": "0.2.2",
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
    add_lineage(created["digest"], {
        "event": "composed",
        "agent": "composer",
        "inputs": req.inputs,
        "timestamp": timestamp(),
    })
    return {"created": created["digest"], "inputs": req.inputs}


@app.post("/agents/execution/run")
def execution_run(req: ExecuteReq):
    return execute_runtime(
        runtime_name=req.runtimeName,
        runtime_object=req.runtimeObject,
        inputs=req.inputs,
        parameters=req.parameters,
    )


@app.post("/workflows/run")
def workflow_run(req: WorkflowRunReq):
    if not req.steps:
        raise HTTPException(status_code=400, detail="Workflow requires at least one step")
    current_inputs = list(req.inputs)
    step_results = []
    workflow_id = str(uuid.uuid4())

    for index, step in enumerate(req.steps, start=1):
        step_inputs = current_inputs if step.usePreviousOutput or index == 1 else list(req.inputs)
        result = execute_runtime(
            runtime_name=step.runtimeName,
            runtime_object=step.runtimeObject,
            inputs=step_inputs,
            parameters={**step.parameters, "workflow_id": workflow_id, "step": index},
        )
        step_results.append({"step": index, **result})
        current_inputs = [result["output"]]

    workflow_record = create_record(
        mediaType="application/vnd.uar.workflow-record+json",
        mode="immutable",
        attributes={"agent": "workflow", "kind": "workflow-record", "workflowName": req.name},
        links=[
            *[{"rel": "initial_input", "target": digest} for digest in req.inputs],
            *[{"rel": "step_output", "target": item["output"]} for item in step_results],
        ],
        content={
            "workflow_id": workflow_id,
            "name": req.name,
            "steps": step_results,
            "final_output": step_results[-1]["output"],
            "timestamp": timestamp(),
        },
    )
    add_lineage(workflow_record["digest"], {
        "event": "workflow_completed",
        "agent": "workflow",
        "workflow_id": workflow_id,
        "final_output": step_results[-1]["output"],
        "timestamp": timestamp(),
    })
    return {
        "status": "completed",
        "workflowRecord": workflow_record["digest"],
        "finalOutput": step_results[-1]["output"],
        "steps": step_results,
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
