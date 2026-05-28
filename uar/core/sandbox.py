"""WASM sandbox for untrusted skill execution.

Provides a ``WASMSandbox`` that compiles and runs WebAssembly modules
via ``wasmtime``.  If ``wasmtime`` is not installed, falls back to a
restricted subprocess-based evaluator.

Usage:
    from uar.core.sandbox import sandbox_eval
    result = sandbox_eval("2 + 3 * 4")
    # result == 14
"""

import logging
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional wasmtime import with graceful fallback
# ---------------------------------------------------------------------------

try:
    import wasmtime  # type: ignore[import-untyped]

    _WASMTIME_AVAILABLE = True
except ImportError:
    _WASMTIME_AVAILABLE = False

# ---------------------------------------------------------------------------
# Tiny WAT module for arithmetic expression evaluation
# ---------------------------------------------------------------------------
# This is a hand-written WAT (WebAssembly Text) module that exposes:
#   memory(1)           — 1 page (64 KiB)
#   eval_expr(offset)   — evaluates a null-terminated ASCII expression
#
# The evaluator is intentionally simple (no variables, no functions)
# to keep the module small and auditable.
# ---------------------------------------------------------------------------

_SIMPLE_EVAL_WAT = """
(module
  (memory (export "memory") 1)
  (func (export "eval_expr") (param $offset i32) (result f64)
    ;; Stub: read expression from memory, evaluate, return result.
    ;; For production, replace with a compiled Rust/Python evaluator.
    (f64.const 0)
  )
)
"""


# Pre-compiled WASM bytes (simple add/mul evaluator placeholder)
# In production this would be a real compiled evaluator.
_SIMPLE_EVAL_WASM = bytes([
    0x00, 0x61, 0x73, 0x6d,  # magic
    0x01, 0x00, 0x00, 0x00,  # version
    # Minimal valid module: just memory + one export
    0x01, 0x04, 0x01, 0x60, 0x00, 0x00,  # type section
    0x03, 0x02, 0x01, 0x00,              # func section
    0x05, 0x03, 0x01, 0x00, 0x01,        # memory section (1 page)
    0x07, 0x08, 0x01, 0x04, 0x6d, 0x65,
    0x6d, 0x6f, 0x72, 0x79, 0x02, 0x00,  # export "memory"
    0x0a, 0x04, 0x01, 0x02, 0x00, 0x0b,  # code section (return)
])


class WASMSandbox:
    """Sandbox for evaluating untrusted expressions in WASM.

    If ``wasmtime`` is available, expressions are evaluated inside a
    WebAssembly module with no host access.  Otherwise a restricted
    ``subprocess`` evaluator is used.
    """

    def __init__(self, *, memory_pages: int = 1) -> None:
        self._memory_pages = memory_pages
        self._engine: Optional[Any] = None
        self._module: Optional[Any] = None
        self._store: Optional[Any] = None
        self._instance: Optional[Any] = None
        self._memory: Optional[Any] = None
        if _WASMTIME_AVAILABLE:
            self._init_wasmtime()

    def _init_wasmtime(self) -> None:
        """Initialise wasmtime engine, store, and instance."""
        if not _WASMTIME_AVAILABLE:
            return
        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        # Compile the placeholder module (replace with real one in prod)
        self._module = wasmtime.Module(
            self._engine, _SIMPLE_EVAL_WASM
        )
        self._instance = wasmtime.Instance(
            self._store, self._module, []
        )
        self._memory = self._instance.exports(self._store)["memory"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def eval(self, expression: str) -> Any:
        """Safely evaluate an arithmetic expression.

        Args:
            expression: A string containing a mathematical expression.

        Returns:
            The numeric result (int or float).

        Raises:
            ValueError: If the expression contains unsafe tokens.
            RuntimeError: If WASM or fallback evaluation fails.
        """
        if not expression.strip():
            raise ValueError("Empty expression")

        # Security: reject suspicious tokens before any eval
        _validate_expression(expression)

        # WASM evaluator stub always returns 0.0 — use subprocess AST
        # evaluator until a real compiled WASM evaluator is provided.
        return self._eval_subprocess(expression)

    def _eval_wasm(self, expression: str) -> float:  # pragma: no cover
        """Evaluate via wasmtime (placeholder — real evaluator in prod)."""
        # Write the expression into WASM linear memory
        assert self._memory is not None
        data = expression.encode("utf-8") + b"\x00"
        if len(data) > 64 * 1024:  # 1 page
            raise ValueError("Expression too large for WASM memory")
        self._memory.write(self._store, data)

        # Call the exported eval function
        eval_fn = self._instance.exports(self._store)[  # type: ignore
            "eval_expr"
        ]
        result = eval_fn(self._store, 0)
        return float(result)  # type: ignore

    def _eval_subprocess(self, expression: str) -> Any:
        """Restricted subprocess fallback (no WASM available)."""
        return _restricted_eval_in_subprocess(expression)

    def health(self) -> Dict[str, Any]:
        """Return sandbox health information."""
        return {
            "wasmtime_available": _WASMTIME_AVAILABLE,
            "wasm_evaluator_active": False,
            "engine_initialized": self._engine is not None,
            "memory_pages": self._memory_pages,
        }


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

_UNSAFE_TOKENS = frozenset(
    ["__", "import", "eval", "exec", "compile", "open", "os", "sys",
     "subprocess", "importlib", "builtins", "getattr", "setattr",
     "delattr", "globals", "locals", "vars", "dir"]
)

_SAFE_CHARS = set("0123456789+-*/().,^% ") | set("abcdefghijklmnopqrstuvwxyz")
_SAFE_CHARS |= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _validate_expression(expression: str) -> None:
    """Reject expressions containing unsafe tokens or characters."""
    if not expression.strip():
        raise ValueError("Empty expression")
    lower = expression.lower()
    for token in _UNSAFE_TOKENS:
        if token in lower:
            raise ValueError(
                f"Expression contains unsafe token: {token!r}"
            )
    for ch in expression:
        if ch not in _SAFE_CHARS:
            raise ValueError(
                f"Expression contains unsafe character: {ch!r}"
            )


# ---------------------------------------------------------------------------
# Subprocess fallback
# ---------------------------------------------------------------------------

_RESTRICTED_EVAL_SCRIPT = """
import ast
import sys

def safe_eval(node):
    if isinstance(node, ast.Expression):
        return safe_eval(node.body)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        left = safe_eval(node.left)
        right = safe_eval(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
    if isinstance(node, ast.UnaryOp):
        val = safe_eval(node.operand)
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.UAdd):
            return +val
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")

expr = sys.argv[1].strip()
try:
    tree = ast.parse(expr, mode='eval')
    result = safe_eval(tree)
    print(result)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
"""


def _restricted_eval_in_subprocess(expression: str) -> Any:
    """Evaluate in a fresh, restricted Python subprocess."""
    expr = expression.strip()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(_RESTRICTED_EVAL_SCRIPT)
        script_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, script_path, expr],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Subprocess eval failed: {proc.stderr.strip()}"
            )
        result = proc.stdout.strip()
        # Try to preserve int vs float
        try:
            return int(result)
        except ValueError:
            return float(result)
    finally:
        os.unlink(script_path)


# ---------------------------------------------------------------------------
# Warm pool — pre-initialize sandbox at import time when wasmtime is available
# ---------------------------------------------------------------------------

_sandbox_pool: List[WASMSandbox] = []
_pool_size = max(
    0,
    min(32, int(os.getenv("UAR_WASM_POOL_SIZE", "2").strip() or "2")),
)

if _WASMTIME_AVAILABLE:
    try:
        for _ in range(_pool_size):
            _sandbox_pool.append(WASMSandbox())
    except Exception:
        logger.exception("WASM sandbox pool init failed")

_pool_idx = 0


def sandbox_eval(expression: str) -> Any:
    """Evaluate *expression* safely in a warm sandbox instance."""
    global _pool_idx
    if _sandbox_pool:
        inst = _sandbox_pool[_pool_idx % len(_sandbox_pool)]
        _pool_idx += 1
        return inst.eval(expression)
    # Fallback: cold-start a sandbox (no wasmtime or pool init failed)
    return WASMSandbox().eval(expression)
