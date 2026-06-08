"""Read-only Model Context Protocol (MCP) server for UAR.

The previous MCP scaffold exposed every registered UAR skill as an invokable
MCP tool. That is useful for experiments, but too broad for operational use.
This server is deny-by-default and exposes only read-only inspection tools.

Usage:
    python -m uar.mcp.server

Environment:
    UAR_MCP_API_URL    Base UAR API URL, default http://127.0.0.1:8000
    UAR_MCP_API_TOKEN  Optional bearer token for guarded endpoints
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict, Mapping

from uar.mcp.tools import UARMCPError, call_tool, get_tools

logger = logging.getLogger("uar.mcp")
JSONRPC_VERSION = "2.0"
_MAX_MCP_PAYLOAD = 10_000_000  # 10 MB safety cap


def _send(msg: Dict[str, Any]) -> None:
    """Write a framed JSON-RPC message to stdout."""
    payload = json.dumps(msg, separators=(",", ":"))
    sys.stdout.write(f"Content-Length: {len(payload)}\r\n\r\n{payload}")
    sys.stdout.flush()


def _recv() -> Dict[str, Any]:
    """Read one framed JSON-RPC message from stdin."""
    headers: Dict[str, str] = {}
    while True:
        line = sys.stdin.readline()
        if not line or line == "\r\n":
            break
        key, _, value = line.strip().partition(":")
        headers[key.strip().lower()] = value.strip()

    length = int(headers.get("content-length", 0))
    if length <= 0:
        return {}
    if length > _MAX_MCP_PAYLOAD:
        raise ValueError("MCP payload too large")

    raw = sys.stdin.read(length)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("MCP message JSON decode failed: %s", exc)
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": msg_id,
        "error": {"code": code, "message": message},
    }


def _handle_initialize(_: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "uar-readonly-mcp-server", "version": "0.1.0"},
    }


def _handle_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in get_tools().values()
        ]
    }


def _handle_tool_call(params: Mapping[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        raise UARMCPError("tools/call requires a string name")
    if not isinstance(arguments, dict):
        raise UARMCPError("tools/call arguments must be an object")

    result = call_tool(name, arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2, sort_keys=True, default=str),
            }
        ],
        "isError": False,
    }


def main() -> None:
    """Run the MCP stdio server loop."""
    logging.basicConfig(level=logging.WARNING, handlers=[logging.StreamHandler(sys.stderr)])
    initialized = False

    while True:
        try:
            req = _recv()
        except Exception as exc:
            logger.warning("MCP receive failed: %s", exc)
            break

        if not req:
            break

        msg_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})
        if not isinstance(params, dict):
            params = {}

        # Notifications have no response.
        if msg_id is None:
            if method == "notifications/initialized":
                initialized = True
            continue

        if method == "initialize":
            initialized = True
            _send({"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": _handle_initialize(params)})
            continue

        if not initialized:
            _send(_error(msg_id, -32002, "Not initialized"))
            continue

        if method == "tools/list":
            _send({"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": _handle_tools_list()})
            continue

        if method == "tools/call":
            try:
                result = _handle_tool_call(params)
                _send({"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": result})
            except UARMCPError as exc:
                _send(_error(msg_id, -32000, str(exc)))
            continue

        _send(_error(msg_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
