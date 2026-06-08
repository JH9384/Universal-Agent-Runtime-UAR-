"""Read-only MCP tool helpers for UAR.

These helpers are transport-agnostic: the stdio MCP shim can call them, tests can
exercise them directly, and future protocol adapters can reuse them without
reaching into API internals.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
READ_ONLY_TOOL_NAMES = {
    "uar.health",
    "uar.mission_control",
    "uar.list_runs",
    "uar.get_run",
    "uar.replay_summary",
    "uar.certification_status",
    "uar.burnin_history",
    "uar.failure_hotspots",
}


@dataclass(frozen=True)
class MCPTool:
    """Description for a read-only UAR MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Mapping[str, Any]], Dict[str, Any]]


class UARMCPError(RuntimeError):
    """Raised when an MCP tool cannot complete safely."""


def _base_url() -> str:
    return os.getenv("UAR_MCP_API_URL", DEFAULT_BASE_URL).rstrip("/") + "/"


def _headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    token = os.getenv("UAR_MCP_API_TOKEN") or os.getenv("UAR_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(path: str) -> Dict[str, Any]:
    url = urljoin(_base_url(), path.lstrip("/"))
    request = Request(url, headers=_headers(), method="GET")
    try:
        with urlopen(request, timeout=float(os.getenv("UAR_MCP_TIMEOUT", "5"))) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {"status": "empty", "url": url}
            decoded = json.loads(body)
            if isinstance(decoded, dict):
                return decoded
            return {"items": decoded}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise UARMCPError(f"GET {path} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise UARMCPError(f"GET {path} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise UARMCPError(f"GET {path} returned non-JSON content") from exc


def _require_string(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UARMCPError(f"Missing required string argument: {key}")
    return value.strip()


def _health(_: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        return _get_json("/api/health")
    except UARMCPError:
        return _get_json("/health")


def _mission_control(_: Mapping[str, Any]) -> Dict[str, Any]:
    return _get_json("/api/uar/mission-control")


def _list_runs(args: Mapping[str, Any]) -> Dict[str, Any]:
    limit = int(args.get("limit", 20))
    limit = max(1, min(limit, 100))
    return _get_json(f"/api/uar/runs?limit={limit}")


def _get_run(args: Mapping[str, Any]) -> Dict[str, Any]:
    run_id = _require_string(args, "run_id")
    return _get_json(f"/api/uar/runs/{run_id}")


def _replay_summary(args: Mapping[str, Any]) -> Dict[str, Any]:
    run_id = _require_string(args, "run_id")
    return _get_json(f"/api/uar/runs/{run_id}/confidence")


def _certification_status(_: Mapping[str, Any]) -> Dict[str, Any]:
    return _get_json("/api/uar/certification/status")


def _burnin_history(args: Mapping[str, Any]) -> Dict[str, Any]:
    limit = int(args.get("limit", 20))
    limit = max(1, min(limit, 100))
    return _get_json(f"/api/uar/burnin/history?limit={limit}")


def _failure_hotspots(_: Mapping[str, Any]) -> Dict[str, Any]:
    return _get_json("/api/uar/analytics/failure-hotspots")


def get_tools() -> Dict[str, MCPTool]:
    """Return the allowlisted read-only MCP tool registry."""

    run_id_schema = {
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
        "additionalProperties": False,
    }
    limit_schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
        "additionalProperties": False,
    }
    empty_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    tools = {
        "uar.health": MCPTool("uar.health", "Read UAR API health status.", empty_schema, _health),
        "uar.mission_control": MCPTool(
            "uar.mission_control", "Read Mission Control snapshot.", empty_schema, _mission_control
        ),
        "uar.list_runs": MCPTool("uar.list_runs", "List recent UAR runs.", limit_schema, _list_runs),
        "uar.get_run": MCPTool("uar.get_run", "Read one UAR run by ID.", run_id_schema, _get_run),
        "uar.replay_summary": MCPTool(
            "uar.replay_summary", "Read replay confidence for a run.", run_id_schema, _replay_summary
        ),
        "uar.certification_status": MCPTool(
            "uar.certification_status", "Read certification status.", empty_schema, _certification_status
        ),
        "uar.burnin_history": MCPTool(
            "uar.burnin_history", "Read burn-in history.", limit_schema, _burnin_history
        ),
        "uar.failure_hotspots": MCPTool(
            "uar.failure_hotspots", "Read failure hotspot analytics.", empty_schema, _failure_hotspots
        ),
    }
    assert set(tools) == READ_ONLY_TOOL_NAMES
    return tools


def call_tool(name: str, arguments: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Call an allowlisted read-only MCP tool by name."""

    tools = get_tools()
    if name not in tools:
        raise UARMCPError(f"Tool is not allowlisted: {name}")
    return tools[name].handler(arguments or {})
