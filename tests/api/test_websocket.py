"""WebSocket integration tests for the /ws/run endpoint.

Covers connection lifecycle, event streaming, schema validation,
error handling, and server-side batching behavior.
"""

import json
import time
from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up test API keys for authenticated endpoints."""
    with patch.dict(
        "uar.api.middleware.API_KEYS",
        {"dev-key-12345": {"user": "developer", "tier": "authenticated"}},
        clear=True,
    ):
        yield


def _extract_events(messages: list) -> list[dict]:
    """Parse raw websocket text messages into event dicts."""
    events = []
    for msg in messages:
        try:
            events.append(json.loads(msg))
        except json.JSONDecodeError:
            pass
    return events


def test_ws_basic_stream():
    """Connect, send a goal, and receive the full event stream."""
    with client.websocket_connect("/ws/run") as ws:
        ws.send_json({"goal": "test ws"})
        messages = []
        # Collect until close or timeout
        start = time.time()
        while time.time() - start < 15:
            try:
                msg = ws.receive_text()
                messages.append(msg)
                # Stop once we see persisted or error
                data = json.loads(msg)
                if data.get("type") in ("persisted", "error"):
                    break
            except Exception:
                break

    events = _extract_events(messages)
    types = [e["type"] for e in events]

    assert "orchestration_plan" in types
    assert "start" in types
    assert "complete" in types
    assert "persisted" in types

    # Validate event schema
    for ev in events:
        assert ev.get("schema_version") == "uar.event.v1"
        assert "run_id" in ev
        assert "goal_id" in ev
        assert "timestamp" in ev
        assert "correlation_id" in ev


def test_ws_invalid_goal_validation():
    """Server should emit an error event for an invalid request."""
    with client.websocket_connect("/ws/run") as ws:
        # Missing required 'goal' field
        ws.send_json({})
        messages = []
        start = time.time()
        while time.time() - start < 5:
            try:
                msg = ws.receive_text()
                messages.append(msg)
                break
            except Exception:
                break

    events = _extract_events(messages)
    assert any(e.get("type") == "error" for e in events)


def test_ws_execution_order_with_recipe():
    """Send execution_order referencing a recipe and verify expansion."""
    payload = {
        "goal": "test recipe over ws",
        "execution_order": [
            {"type": "recipe", "content": "review", "id": "r1"},
        ],
    }
    with client.websocket_connect("/ws/run") as ws:
        ws.send_json(payload)
        messages = []
        start = time.time()
        while time.time() - start < 15:
            try:
                msg = ws.receive_text()
                messages.append(msg)
                data = json.loads(msg)
                if data.get("type") in ("persisted", "error"):
                    break
            except Exception:
                break

    events = _extract_events(messages)
    types = [e["type"] for e in events]

    assert "orchestration_plan" in types
    assert "start" in types
    assert "complete" in types


def test_ws_metrics_event_emitted():
    """Verify the executor emits a metrics event before completion."""
    with client.websocket_connect("/ws/run") as ws:
        ws.send_json({"goal": "test metrics"})
        messages = []
        start = time.time()
        while time.time() - start < 15:
            try:
                msg = ws.receive_text()
                messages.append(msg)
                data = json.loads(msg)
                if data.get("type") in ("persisted", "error"):
                    break
            except Exception:
                break

    events = _extract_events(messages)
    metrics_events = [e for e in events if e.get("type") == "metrics"]
    assert len(metrics_events) >= 1

    payload = metrics_events[0].get("payload", {})
    assert "total_time_sec" in payload
    assert "event_count" in payload
    assert "cache_hits" in payload
    assert "cache_misses" in payload


def test_ws_heartbeat_interval():
    """Server should send heartbeat events during long executions.

    We patch the heartbeat interval to a very short value so the
    test completes quickly.
    """
    with patch("uar.api.server.WS_HEARTBEAT_INTERVAL", 0):
        with client.websocket_connect("/ws/run") as ws:
            ws.send_json({"goal": "test heartbeat"})
            messages = []
            start = time.time()
            while time.time() - start < 10:
                try:
                    msg = ws.receive_text()
                    messages.append(msg)
                    data = json.loads(msg)
                    if data.get("type") in ("persisted", "error"):
                        break
                except Exception:
                    break

    events = _extract_events(messages)
    heartbeats = [e for e in events if e.get("type") == "heartbeat"]
    # With interval=0 heartbeat fires immediately on each loop iteration
    assert len(heartbeats) >= 1


def test_ws_event_limit_enforced():
    """Server should stop streaming when MAX_STREAM_EVENTS is exceeded.

    We patch the limit to a tiny value so the test triggers it.
    """
    import uar.api.server as server_mod

    with patch.object(server_mod._exec_svc, "max_stream_events", 3):
        with client.websocket_connect("/ws/run") as ws:
            ws.send_json({"goal": "test limit"})
            messages = []
            start = time.time()
            while time.time() - start < 10:
                try:
                    msg = ws.receive_text()
                    messages.append(msg)
                    data = json.loads(msg)
                    if data.get("type") == "error":
                        break
                except Exception:
                    break

    events = _extract_events(messages)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) >= 1
    assert "limit reached" in error_events[0].get("error", "").lower()


def test_ws_batching_accumulates_and_flushes():
    """Events should be delivered even with small batch thresholds.

    We patch batch size to 2 and timeout to 0.01s to force frequent
    flushes so the test does not hang.
    """
    with patch("uar.api.server.WS_BATCH_SIZE", 2):
        with patch("uar.api.server.WS_BATCH_TIMEOUT", 0.01):
            with client.websocket_connect("/ws/run") as ws:
                ws.send_json({"goal": "test batching"})
                messages = []
                start = time.time()
                while time.time() - start < 10:
                    try:
                        msg = ws.receive_text()
                        messages.append(msg)
                        data = json.loads(msg)
                        if data.get("type") in ("persisted", "error"):
                            break
                    except Exception:
                        break

    events = _extract_events(messages)
    # Should still receive the full flow despite tiny batches
    types = [e["type"] for e in events]
    assert "orchestration_plan" in types
    assert "complete" in types
    assert "persisted" in types
