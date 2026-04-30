from __future__ import annotations

import ast
import multiprocessing as mp
import queue
import resource
from typing import Any

from fastapi import HTTPException

DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_MEMORY_MB = 128

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


def object_value(obj: dict[str, Any]) -> Any:
    content = obj.get("content")
    if isinstance(content, dict) and set(content.keys()) == {"result"}:
        return content["result"]
    return content


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
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_CPU, (2, 2))

        local_scope = {
            "inputs": input_objects,
            "parameters": parameters,
            "contents": [obj.get("content") for obj in input_objects],
            "values": [object_value(obj) for obj in input_objects],
            "attributes": [obj.get("attributes", {}) for obj in input_objects],
        }
        result = eval(code, {"__builtins__": ALLOWED_BUILTINS}, local_scope)
        result_queue.put({"ok": True, "result": result})
    except BaseException as exc:
        result_queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_code(
    code: str,
    input_objects: list[dict[str, Any]],
    parameters: dict[str, Any] | None = None,
) -> Any:
    parameters = parameters or {}
    validate_code(code)

    timeout_seconds = float(parameters.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    memory_mb = int(parameters.get("memory_mb", DEFAULT_MEMORY_MB))
    timeout_seconds = max(0.1, min(timeout_seconds, 10.0))
    memory_mb = max(32, min(memory_mb, 512))

    result_queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(
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
