#!/usr/bin/env python3
"""Smoke-check the read-only UAR MCP server without needing an MCP client."""

from __future__ import annotations

from uar.mcp.tools import get_tools


def main() -> int:
    tools = get_tools()
    required = {
        "uar.health",
        "uar.mission_control",
        "uar.list_runs",
        "uar.get_run",
        "uar.replay_summary",
        "uar.certification_status",
        "uar.burnin_history",
        "uar.failure_hotspots",
    }
    missing = sorted(required - set(tools))
    extra = sorted(set(tools) - required)
    if missing or extra:
        print(f"MCP smoke failed: missing={missing} extra={extra}")
        return 1
    for name, tool in sorted(tools.items()):
        if not tool.input_schema.get("type") == "object":
            print(f"MCP smoke failed: invalid input schema for {name}")
            return 1
        print(f"{name}: {tool.description}")
    print("MCP smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
