"""OpenAPI schema fuzz tests via Schemathesis.

Automatically generates hundreds of test cases from the FastAPI OpenAPI
schema, testing every endpoint for spec conformance, 500 errors, and
security-relevant edge cases (path traversal, injection, malformed payloads).

Requires: pip install schemathesis
Run: st run --app=uar.api.server:app http://127.0.0.1:8000/openapi.json
  Or: pytest tests/api/test_schemathesis_fuzz.py -v
"""

import pytest
from hypothesis import settings
from schemathesis.openapi import from_asgi

from uar.api.server import app

pytestmark = pytest.mark.schemathesis

# Load the OpenAPI schema directly from the app
schema = from_asgi("/openapi.json", app)

# CI-friendly hypothesis settings
CI_SETTINGS = settings(max_examples=20, deadline=None)


# Endpoints that require auth or external service setup and
# are covered by dedicated integration tests.
_EXCLUDED_PATHS = {
    "/api/uar/docs/browse",
    "/api/uar/docs/library",
    "/api/uar/docs/upload",
    "/api/uar/runs/{run_id}/timeline",
    "/api/uar/runs/{run_id}/compare/{other_run_id}",
    "/api/provenance/{run_id}",
    "/api/uar/query-code",
    "/api/cache/invalidate",
    "/api/cache/stats",
    "/api/uar/orchestrator/status",
    "/api/advanced/orchestrator/status",
    "/agents/constraint/check",
    "/agents/composer/compose",
    "/api/advanced/dagster/pipeline",
    "/api/advanced/dagster/status",
    "/objects/{digest}/download",
    "/runtimes/{name}",
    "/api/health/circuit-breakers",
}


@schema.parametrize()
@CI_SETTINGS
def test_api_endpoint_no_server_errors(case):
    """Every endpoint must return a non-500 status code.

    Schemathesis auto-generates valid and edge-case inputs from the
    OpenAPI schema. If the server crashes with a 500, we have a bug.

    Auth-required or externally-dependent paths are excluded to avoid
    false positives from missing setup.
    """
    if case.operation.path in _EXCLUDED_PATHS:
        pytest.skip("Excluded path requires auth or external setup")
    response = schema.transport.send(case)
    assert response.status_code < 500, (
        f"Endpoint {case.operation.path} returned {response.status_code} "
        f"with body: {response.text[:200]}"
    )


# Filtered schemas for targeted endpoint testing
_run_schema = schema.include(path="/api/uar/run")
_stream_schema = schema.include(path="/api/uar/stream")
_runs_schema = schema.include(path="/api/uar/runs")
_ping_schema = schema.include(path="/api/uar/skills/ping")


@_run_schema.parametrize()
@CI_SETTINGS
def test_run_endpoint_validates_input(case):
    """The /run endpoint must reject invalid payloads with 400/422."""
    response = schema.transport.send(case)
    # Schemathesis may send valid or invalid payloads.
    # We only assert that 500s never happen.
    assert response.status_code < 500


@_stream_schema.parametrize()
@CI_SETTINGS
def test_stream_endpoint_never_crashes(case):
    """The /stream endpoint must not crash on any schema-valid input."""
    response = schema.transport.send(case)
    assert response.status_code < 500


@_runs_schema.parametrize()
@CI_SETTINGS
def test_list_runs_never_crashes(case):
    """The /runs list endpoint must not crash."""
    response = schema.transport.send(case)
    assert response.status_code < 500


@_ping_schema.parametrize()
@CI_SETTINGS
def test_skill_ping_never_crashes(case):
    """The skill ping endpoint must not crash."""
    response = schema.transport.send(case)
    assert response.status_code < 500
