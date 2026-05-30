"""Frontend-backend API contract validation.

Ensures the FastAPI OpenAPI schema is valid and contains all
endpoints the frontend expects. This catches drift between
backend routes and frontend API clients early.
"""

import pytest
from fastapi.testclient import TestClient

from uar.api.responses import error_response, error_detail_response
from uar.api.server import app

# Endpoints that the frontend TypeScript client is known to call.
# Keep this list in sync with apps/web/src/api/client.ts or similar.
EXPECTED_ENDPOINTS = {
    ("GET", "/api/uar/skills"),
    ("GET", "/api/uar/recipes"),
    ("POST", "/api/uar/run"),
    ("POST", "/api/uar/stream"),
    ("GET", "/api/health"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/status"),
    ("GET", "/api/metrics"),
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_openapi_schema_is_valid(client):
    """The generated OpenAPI schema must be valid JSON and contain paths."""
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    assert "paths" in schema
    assert len(schema["paths"]) > 0


def test_expected_endpoints_exist(client):
    """All frontend-known endpoints must be present in the OpenAPI schema."""
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    missing = []
    for method, path in EXPECTED_ENDPOINTS:
        route = paths.get(path, {})
        if method.lower() not in route:
            missing.append(f"{method} {path}")
    assert not missing, f"Missing endpoints in OpenAPI schema: {missing}"


def test_all_error_responses_have_request_id(client):
    """Custom error response schemas should include request_id field."""
    schema = client.get("/openapi.json").json()
    # Walk all response schemas looking for error responses
    components = schema.get("components", {}).get("schemas", {})
    for name, defn in components.items():
        if "error" not in name.lower():
            continue
        # Skip FastAPI built-in schemas
        if name in {"HTTPValidationError", "ValidationError"}:
            continue
        props = defn.get("properties", {})
        assert (
            "request_id" in props or "requestId" in props
        ), f"Schema {name} missing request_id"


def test_run_request_has_execution_order(client):
    """RunRequest schema must include the execution_order field."""
    schema = client.get("/openapi.json").json()
    components = schema.get("components", {}).get("schemas", {})
    run_req = components.get("RunRequest", {})
    props = run_req.get("properties", {})
    assert (
        "execution_order" in props
    ), "RunRequest missing execution_order field"


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def test_error_response_with_request_id():
    """error_response must include request_id when provided."""
    resp = error_response(
        400, "BAD", "bad request", request_id="req-123"
    )
    assert resp.status_code == 400
    assert (
        resp.body
        == b'{"error":"BAD","message":"bad request","request_id":"req-123"}'
    )


def test_error_response_without_request_id():
    """error_response must omit request_id when not provided."""
    resp = error_response(500, "ERR", "oops")
    assert resp.status_code == 500
    body = resp.body
    assert b"request_id" not in body


def test_error_detail_response_without_request_id():
    """error_detail_response must wrap payload in 'detail' key."""
    resp = error_detail_response(400, "BAD", "bad request")
    assert resp.status_code == 400
    assert b'"detail"' in resp.body
    assert b"request_id" not in resp.body


def test_error_detail_response_with_request_id():
    """error_detail_response must include request_id when provided."""
    resp = error_detail_response(
        500, "ERR", "oops", request_id="req-456"
    )
    assert resp.status_code == 500
    assert b'"detail"' in resp.body
    assert b"req-456" in resp.body
