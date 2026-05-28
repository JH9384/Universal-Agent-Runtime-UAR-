"""Model Context Protocol (MCP) server for UAR skills.

Exposes every registered UAR skill as an MCP tool so Claude, Cursor,
Copilot, and other MCP-compatible clients can invoke them.

Usage:
    python -m uar.mcp.server

The server communicates via JSON-RPC 2.0 over stdio as per the
Model Context Protocol specification.
"""

import json
import logging
import sys
from typing import Any, Dict, List

from uar.core.registry import registry

import uar.skills  # noqa: F401 — registers all standard skills

logger = logging.getLogger("uar.mcp")


def _send(msg: Dict[str, Any]) -> None:
    """Write a JSON-RPC message to stdout."""
    payload = json.dumps(msg, separators=(",", ":"))
    sys.stdout.write(f"Content-Length: {len(payload)}\r\n\r\n{payload}")
    sys.stdout.flush()


def _recv() -> Dict[str, Any]:
    """Read a JSON-RPC message from stdin."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line or line == "\r\n":
            break
        key, _, value = line.strip().partition(":")
        headers[key.strip().lower()] = value.strip()

    length = int(headers.get("content-length", 0))
    if length <= 0:
        return {}
    _MAX_MCP_PAYLOAD = 10_000_000  # 10 MB safety cap
    if length > _MAX_MCP_PAYLOAD:
        raise ValueError("MCP payload too large")

    raw = sys.stdin.read(length)
    return json.loads(raw)


def _build_tool(name: str, fn: Any) -> Dict[str, Any]:
    """Create an MCP tool definition from a UAR skill."""
    doc = (fn.__doc__ or "").strip()
    # Truncate description to first sentence for MCP
    desc = doc.split(".")[0] + "." if doc else f"UAR skill: {name}"
    return {
        "type": "tool",
        "name": name,
        "description": desc[:200],
        "inputSchema": {
            "type": "object",
            "properties": {
                "metadata": {
                    "type": "object",
                    "description": "Goal metadata dict (key-value params)",
                },
            },
            "required": ["metadata"],
        },
    }


def _handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Respond to MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True},
        },
        "serverInfo": {
            "name": "uar-mcp-server",
            "version": "1.1.0",
        },
    }


def _handle_tools_list() -> List[Dict[str, Any]]:
    """Return all registered UAR skills as MCP tools."""
    tools = []
    for name in registry.list():
        try:
            fn = registry.get(name)
            tools.append(_build_tool(name, fn))
        except Exception:
            logger.warning("Skipping skill %s: not callable", name)
    return tools


def _handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a UAR skill and return MCP-compliant content."""
    try:
        fn = registry.get(name)
    except Exception as exc:
        logger.exception("Skill lookup failed")
        return {
            "content": [{"type": "text", "text": f"Skill error: {exc}"}],
            "isError": True,
        }

    # Build a minimal PipelineContext-like object
    class _FakeContext:
        def __init__(self, metadata: Dict[str, Any]) -> None:
            class _FakeGoal:
                def __init__(self, meta: Dict[str, Any]) -> None:
                    self.metadata = meta
            self.goal = _FakeGoal(metadata)
            self.data: Dict[str, Any] = {}

    ctx = _FakeContext(arguments.get("metadata", {}))
    try:
        result = fn(ctx)
        text = json.dumps(result, indent=2, default=str)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": result.get("status") == "failed",
        }
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"Execution error: {exc}"}],
            "isError": True,
        }


def main() -> None:
    """Run the MCP stdio server loop."""
    logging.basicConfig(
        level=logging.WARNING,
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    initialized = False

    while True:
        try:
            req = _recv()
        except Exception:
            break

        if not req:
            break

        msg_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        # Notifications (no id) — just ack
        if msg_id is None:
            continue

        if method == "initialize":
            result = _handle_initialize(params)
            initialized = True
            _send({"jsonrpc": "2.0", "id": msg_id, "result": result})
            continue

        if not initialized:
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32002, "message": "Not initialized"},
            })
            continue

        if method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": _handle_tools_list()},
            })

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = _handle_tool_call(name, arguments)
            _send({"jsonrpc": "2.0", "id": msg_id, "result": result})

        else:
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            })


if __name__ == "__main__":
    main()
