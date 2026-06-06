"""Tests for T9 — API Normalization.

Covers:
- success_response envelope shape
- list_response envelope shape
- error_response envelope shape
- error_detail_response envelope shape
- X-API-Version header on responses
- ErrorResponse model schema
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from uar.api.models import ErrorResponse
from uar.api.responses import (
    error_detail_response,
    error_response,
    list_response,
    success_response,
)


def test_success_response_shape():
    """success_response wraps payload in ``data`` key."""
    resp = success_response(data={"status": "ok"})
    assert resp.status_code == 200
    assert resp.body == b'{"data":{"status":"ok"}}'


def test_success_response_with_meta():
    """success_response includes meta when provided."""
    resp = success_response(data={}, meta={"page": 1})
    body = resp.body.decode("utf-8")
    assert '"data":{}' in body
    assert '"meta":{"page":1}' in body


def test_list_response_shape():
    """list_response wraps items with pagination metadata."""
    resp = list_response([1, 2, 3], total=10, page=1, page_size=20)
    assert resp.status_code == 200
    data = resp.body.decode("utf-8")
    assert '"items":[1,2,3]' in data
    assert '"total":10' in data
    assert '"page":1' in data
    assert '"page_size":20' in data


def test_list_response_defaults_total():
    """list_response defaults total to len(items)."""
    resp = list_response([1, 2])
    assert '"total":2' in resp.body.decode("utf-8")


def test_error_response_shape():
    """error_response contains error and message."""
    resp = error_response(400, "bad_request", "Invalid input")
    assert resp.status_code == 400
    body = resp.body.decode("utf-8")
    assert '"error":"bad_request"' in body
    assert '"message":"Invalid input"' in body


def test_error_response_with_code_and_request_id():
    """error_response includes optional code and request_id."""
    resp = error_response(
        500, "internal", "Oops", code="ERR_001", request_id="abc"
    )
    body = resp.body.decode("utf-8")
    assert '"code":"ERR_001"' in body
    assert '"request_id":"abc"' in body


def test_error_detail_response_shape():
    """error_detail_response wraps in ``detail`` key."""
    resp = error_detail_response(400, "validation", "Bad field")
    body = resp.body.decode("utf-8")
    assert body == '{"detail":{"error":"validation","message":"Bad field"}}'


def test_api_version_header():
    """X-API-Version header is present on responses."""
    from uar.api.server import app

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "x-api-version" in resp.headers
    assert resp.headers["x-api-version"]  # non-empty


def test_error_response_model_schema():
    """ErrorResponse model matches normalized envelope."""
    model = ErrorResponse(
        error="test_error", message="Test message", code="TEST_001"
    )
    assert model.error == "test_error"
    assert model.message == "Test message"
    assert model.code == "TEST_001"
    assert model.request_id is None
    assert model.field is None
