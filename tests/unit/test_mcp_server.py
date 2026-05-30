"""Tests for uar.mcp.server."""

from io import StringIO
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


def test_send_writes_content_length():
    """_send must output Content-Length header and JSON payload."""
    import sys

    buf = StringIO()
    with patch.object(sys, "stdout", buf):
        _send({"jsonrpc": "2.0", "id": 1})
    output = buf.getvalue()
    assert "Content-Length:" in output
    assert "jsonrpc" in output


def test_recv_empty_headers():
    """_recv with empty input must return empty dict."""
    import sys

    buf = StringIO("\r\n")
    with patch.object(sys, "stdin", buf):
        result = _recv()
    assert result == {}


def test_recv_too_large_payload():
    """_recv must reject payloads over 10MB."""
    import sys

    buf = StringIO("Content-Length: 20000000\r\n\r\n")
    with patch.object(sys, "stdin", buf):
        with pytest.raises(ValueError, match="too large"):
            _recv()


def test_recv_invalid_json():
    """_recv must return empty dict for invalid JSON."""
    import sys

    buf = StringIO("Content-Length: 5\r\n\r\nnot{j")
    with patch.object(sys, "stdin", buf):
        result = _recv()
    assert result == {}


def test_build_tool_with_doc():
    """_build_tool must create tool definition from skill function."""

    def example_skill(ctx):
        """Example skill. Does something useful."""
        pass

    tool = _build_tool("example", example_skill)
    assert tool["type"] == "tool"
    assert tool["name"] == "example"
    assert "Example skill" in tool["description"]
    assert tool["inputSchema"]["required"] == ["metadata"]


def test_build_tool_without_doc():
    """_build_tool must handle missing docstring."""
    def no_doc_fn(ctx):
        pass

    tool = _build_tool("no_doc", no_doc_fn)
    assert "UAR skill: no_doc" in tool["description"]


def test_handle_initialize():
    """_handle_initialize must return protocol info."""
    result = _handle_initialize({})
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "uar-mcp-server"


def test_handle_tools_list():
    """_handle_tools_list must return tools for registered skills."""
    tools = _handle_tools_list()
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_handle_tool_call_unknown_skill():
    """_handle_tool_call for unknown skill must return error."""
    result = _handle_tool_call("definitely_not_a_skill_12345", {})
    assert result["isError"] is True
    assert "Skill error" in result["content"][0]["text"]


def test_handle_tool_call_skill_error():
    """_handle_tool_call where skill raises must return error."""

    def bad_skill(ctx):
        raise RuntimeError("boom")

    with patch("uar.mcp.server.registry.get", return_value=bad_skill):
        result = _handle_tool_call("bad", {"metadata": {}})
    assert result["isError"] is True
    assert "Execution error" in result["content"][0]["text"]
