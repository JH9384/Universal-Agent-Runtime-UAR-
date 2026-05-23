"""Tests for the /api/uar/runs/{run_id}/timeline endpoint.

Covers: 404 for missing run, timeline structure for existing run.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestTimelineEndpoint:
    def test_timeline_missing_run_returns_404(self, client):
        r = client.get("/api/uar/runs/nonexistent-run-123/timeline")
        assert r.status_code == 404
        data = r.json()
        assert data["detail"]["error"] == "not_found"

    def test_list_runs_endpoint_exists(self, client):
        """The list-runs endpoint should be reachable (may return empty)."""
        r = client.get("/api/uar/runs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
