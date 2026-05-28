"""Tests for MCP server JSON-RPC handlers.

Uses monkey-patched stdin/stdout to avoid actual stdio
and exercises all message handlers.
"""

import io
import json
import sys
from unittest.mock import patch

import pytest

from uar.mcp.server import (
    _send,
    _recv,
    _build_tool,
    _handle_initialize,
    _handle_tools_list,
    _handle_tool_call,
)


class TestSendReceive:
    """Low-level JSON-RPC framing."""

    def test_send_writes_content_length(self, capsys):
        with patch("sys.stdout", new_callable=io.StringIO):
            _send({"jsonrpc": "2.0", "id": 1, "result": {}})
            out = sys.stdout.getvalue()
            assert "Content-Length:" in out
            assert "jsonrpc" in out

    def test_recv_reads_headers_and_body(self, monkeypatch):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1})
        raw = f"Content-Length: {len(payload)}\r\n\r\n{payload}"
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        msg = _recv()
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1

    def test_recv_empty_headers_returns_empty(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        assert _recv() == {}

    def test_recv_payload_too_large(self, monkeypatch):
        payload = "x" * 11_000_000
        raw = f"Content-Length: {len(payload)}\r\n\r\n{payload}"
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        with pytest.raises(ValueError, match="too large"):
            _recv()

    def test_recv_invalid_json_returns_empty(self, monkeypatch):
        raw = "Content-Length: 5\r\n\r\n{bad"
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        assert _recv() == {}


class TestBuildTool:
    """Tool definition generation."""

    def test_build_tool_basic(self):
        def sample_skill():
            """Do something useful."""
            pass

        tool = _build_tool("sample", sample_skill)
        assert tool["type"] == "tool"
        assert tool["name"] == "sample"
        assert "Do something useful" in tool["description"]
        assert "metadata" in tool["inputSchema"]["properties"]
        assert tool["inputSchema"]["required"] == ["metadata"]

    def test_build_tool_no_doc(self):
        def sample_skill():
            pass

        tool = _build_tool("sample", sample_skill)
        assert "UAR skill: sample" in tool["description"]

    def test_build_tool_description_truncated(self):
        def sample_skill():
            """First sentence. Second sentence. Third."""
            pass

        tool = _build_tool("sample", sample_skill)
        assert tool["description"].endswith(".")
        assert "Second" not in tool["description"]

    def test_build_tool_description_max_length(self):
        def sample_skill():
            """A" + "B" * 300 + "."""
            pass

        tool = _build_tool("sample", sample_skill)
        assert len(tool["description"]) <= 200


class TestHandleInitialize:
    """MCP initialize handshake."""

    def test_initialize_returns_protocol_version(self):
        result = _handle_initialize({})
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "uar-mcp-server"


class TestHandleToolsList:
    """Tool listing."""

    def test_lists_registered_skills(self):
        tools = _handle_tools_list()
        names = {t["name"] for t in tools}
        assert "math_compute" in names
        assert all(t["type"] == "tool" for t in tools)

    def test_tools_have_required_schema(self):
        tools = _handle_tools_list()
        for tool in tools:
            assert "inputSchema" in tool
            assert "metadata" in tool["inputSchema"]["properties"]


class TestHandleToolCall:
    """Tool invocation."""

    def test_call_existing_skill(self):
        result = _handle_tool_call(
            "math_compute",
            {
                "metadata": {
                    "math_operation": "evaluate",
                    "math_expression": "2+2",
                },
            },
        )
        assert result["isError"] is False
        assert result["content"][0]["type"] == "text"
        assert "4" in result["content"][0]["text"]

    def test_call_missing_skill(self):
        result = _handle_tool_call(
            "nonexistent_skill_xyz",
            {"metadata": {}},
        )
        assert result["isError"] is True
        assert "Skill error" in result["content"][0]["text"]

    def test_call_skill_execution_error(self):
        """Skill that raises returns isError=True."""
        def bad_skill(ctx):
            raise ValueError("boom")

        from uar.core.registry import registry
        registry.register("__test_bad", bad_skill)
        try:
            result = _handle_tool_call("__test_bad", {"metadata": {}})
            assert result["isError"] is True
            assert "Execution error" in result["content"][0]["text"]
        finally:
            del registry._skills["__test_bad"]

    def test_call_skill_failed_status(self):
        """Skill returning status=failed sets isError=True."""
        def failing_skill(ctx):
            return {"status": "failed", "error": "bad input"}

        from uar.core.registry import registry
        registry.register("__test_fail", failing_skill)
        try:
            result = _handle_tool_call(
                "__test_fail", {"metadata": {}}
            )
            assert result["isError"] is True
        finally:
            del registry._skills["__test_fail"]
