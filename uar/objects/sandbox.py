"""AST-validated subprocess sandbox for UOR runtime code objects.

Code objects ("runtimes") are tiny pure expressions registered by clients
(e.g. ``sum(values)``, ``max(values)``) that can be applied to lists of
input UOR objects. Execution is sandboxed in a child process with:

- An explicit AST allowlist (no imports, attribute access, comprehensions,
  lambdas, or other constructs that could escape).
- An allowlist of names and builtins.
- Best-effort RLIMIT_AS / RLIMIT_CPU enforcement (skipped on macOS where
  these are not honoured for the parent ``maxima``).
- A hard timeout enforced by the parent.
"""

from __future__ import annotations

import ast
import logging
import multiprocessing as mp
import queue
import resource
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_SECONDS = 2.0
DEFAULT_MEMORY_MB = 128
MIN_TIMEOUT_SECONDS = 0.1
MAX_TIMEOUT_SECONDS = 10.0
MIN_MEMORY_MB = 32
MAX_MEMORY_MB = 512


class SandboxError(Exception):
    """Raised when sandbox validation or execution fails."""


ALLOWED_BUILTINS = {
    "len": len,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sorted": sorted,
}

ALLOWED_NAMES = frozenset(
    {
        "inputs",
        "parameters",
        "contents",
        "values",
        "attributes",
        *ALLOWED_BUILTINS.keys(),
    }
)

ALLOWED_AST_NODES: tuple[type, ...] = (
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


# Use fork on POSIX so child processes inherit the parent interpreter
# (including ad-hoc test-loaded modules). macOS defaults to spawn which
# breaks importlib-based test fixtures.
try:
    _MP_CTX: Any = mp.get_context("fork")
except ValueError:  # pragma: no cover - platforms without fork
    _MP_CTX = mp.get_context()


def validate_code(code: str) -> None:
    """Parse ``code`` and reject anything outside the AST allowlist.

    Raises :class:`SandboxError` on any disallowed syntax or name.
    """
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as exc:
        raise SandboxError(f"Invalid runtime syntax: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise SandboxError(
                f"Disallowed syntax: {type(node).__name__}"
            )
        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES:
            raise SandboxError(f"Disallowed name: {node.id}")
        if isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in ALLOWED_BUILTINS
            ):
                raise SandboxError(
                    "Only approved builtin calls are allowed"
                )


def _object_value(obj: Dict[str, Any]) -> Any:
    """Unwrap ``content`` shape ``{"result": x}`` to ``x`` for chaining."""
    content = obj.get("content")
    if isinstance(content, dict) and set(content.keys()) == {"result"}:
        return content["result"]
    return content


def _safe_child_exec(
    code: str,
    input_objects: List[Dict[str, Any]],
    parameters: Dict[str, Any],
    memory_mb: int,
    result_queue: "mp.Queue[Dict[str, Any]]",
) -> None:
    """Run ``code`` inside the child process under best-effort rlimits."""
    try:
        if hasattr(resource, "setrlimit"):
            memory_bytes = int(memory_mb) * 1024 * 1024
            for _res, _vals in (
                (resource.RLIMIT_AS, (memory_bytes, memory_bytes)),
                (resource.RLIMIT_CPU, (2, 2)),
            ):
                try:
                    resource.setrlimit(_res, _vals)
                except (ValueError, OSError):
                    # macOS / sandboxes may reject; safety becomes
                    # advisory rather than enforced.
                    pass
        local_scope = {
            "inputs": input_objects,
            "parameters": parameters,
            "contents": [obj.get("content") for obj in input_objects],
            "values": [_object_value(obj) for obj in input_objects],
            "attributes": [
                obj.get("attributes", {}) for obj in input_objects
            ],
        }
        # eval is intentional and gated by validate_code's AST allowlist.
        result = eval(  # noqa: S307
            code, {"__builtins__": ALLOWED_BUILTINS}, local_scope
        )
        result_queue.put({"ok": True, "result": result})
    except BaseException as exc:  # noqa: BLE001 - report all failures
        # Child must never leak exceptions outward.
        result_queue.put(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        )


def run_code(
    code: str,
    input_objects: List[Dict[str, Any]],
    parameters: Dict[str, Any],
) -> Any:
    """Validate, sandbox, and execute ``code`` against ``input_objects``.

    Returns the produced value or raises :class:`SandboxError` on
    timeout, missing result, or child error.
    """
    validate_code(code)

    timeout_seconds = float(
        parameters.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    )
    memory_mb = int(parameters.get("memory_mb", DEFAULT_MEMORY_MB))
    timeout_seconds = max(
        MIN_TIMEOUT_SECONDS, min(timeout_seconds, MAX_TIMEOUT_SECONDS)
    )
    memory_mb = max(MIN_MEMORY_MB, min(memory_mb, MAX_MEMORY_MB))

    result_queue: "mp.Queue[Dict[str, Any]]" = _MP_CTX.Queue(maxsize=1)
    process = _MP_CTX.Process(
        target=_safe_child_exec,
        args=(code, input_objects, parameters, memory_mb, result_queue),
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(0.5)
        raise SandboxError("Execution timed out")

    try:
        payload = result_queue.get_nowait()
    except queue.Empty as exc:
        raise SandboxError("Execution failed without result") from exc

    if not payload.get("ok"):
        raise SandboxError(
            f"Execution failed: {payload.get('error')}"
        )
    return payload.get("result")


__all__ = [
    "ALLOWED_AST_NODES",
    "ALLOWED_BUILTINS",
    "ALLOWED_NAMES",
    "DEFAULT_MEMORY_MB",
    "DEFAULT_TIMEOUT_SECONDS",
    "SandboxError",
    "run_code",
    "validate_code",
]
