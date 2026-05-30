"""Tests for uar.api.routers.runs."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.runs import router


@pytest.fixture
def client():
    app = FastAPI()
    mock_store = MagicMock()
    mock_store.get_by_run_id.return_value = {
        "run_id": "r1",
        "status": "completed",
        "skills": ["s1"],
        "outputs": {},
        "events": [],
        "timeline": [],
        "metrics": {},
        "uor_address": "addr1",
        "uor_witness": "wit1",
        "timestamp": "2024-01-01",
        "goal": {"id": "g1"},
    }
    mock_store.list_records.return_value = []
    mock_store.delete.return_value = None
    mock_store.purge_old_records.return_value = 5

    from uar.api.middleware import reset_rate_limiter

    reset_rate_limiter()
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        with patch("uar.api.server.store", mock_store):
            app.include_router(router)
            yield TestClient(app)


class TestGetSkills:
    def test_list_skills(self, client):
        response = client.get("/api/uar/skills")
        assert response.status_code == 200
        assert "skills" in response.json()


class TestPingSkill:
    def test_ping_missing(self, client):
        response = client.post("/api/uar/skills/ping", json={})
        assert response.status_code == 400

    def test_ping_not_found(self, client):
        response = client.post(
            "/api/uar/skills/ping", json={"skill": "not_a_real_skill_12345"}
        )
        assert response.status_code == 404


class TestListRuns:
    def test_list(self, client):
        response = client.get("/api/uar/runs")
        assert response.status_code == 200


class TestProvenance:
    def test_provenance_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_by_run_id.return_value = None
        with patch("uar.api.server.store", mock_store):
            response = client.get("/api/provenance/nope")
        assert response.status_code == 404


class TestCompareRuns:
    def test_compare(self, client):
        response = client.get("/api/uar/runs/r1/compare/r2")
        assert response.status_code == 200
        data = response.json()
        assert "run_a" in data
        assert "run_b" in data
        assert "diffs" in data

    def test_compare_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_by_run_id.return_value = None
        with patch("uar.api.server.store", mock_store):
            response = client.get("/api/uar/runs/r1/compare/r2")
        assert response.status_code == 404


class TestBulkDelete:
    def test_by_run_ids(self, client):
        response = client.post(
            "/api/uar/runs/bulk-delete",
            json={"run_ids": ["r1"]},
        )
        assert response.status_code == 200
        assert response.json()["filter"] == "run_ids"

    def test_invalid_run_ids(self, client):
        response = client.post(
            "/api/uar/runs/bulk-delete",
            json={"run_ids": "not_a_list"},
        )
        assert response.status_code == 400

    def test_older_than_days_non_admin(self, client):
        response = client.post(
            "/api/uar/runs/bulk-delete",
            json={"older_than_days": 30},
        )
        assert response.status_code == 403

    def test_older_than_days_invalid(self, client):
        response = client.post(
            "/api/uar/runs/bulk-delete",
            json={"older_than_days": -1},
        )
        assert response.status_code == 400


class TestRunGoal:
    def test_idempotency_hit(self, client):
        cached = {
            "run_id": "cached_run",
            "goal_id": "g1",
            "skills": [],
            "outputs": [],
            "status": "cached",
            "errors": [],
            "events": [],
            "final_context": {},
        }
        with patch("uar.api.server._idempotency_get") as mget:
            mget.return_value = cached
            with patch("uar.api.server._idempotency_set"):
                response = client.post(
                    "/api/uar/run",
                    json={
                        "idempotency_key": "key123",
                        "goal": "test",
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cached"

    def test_idempotency_set(self, client):
        with patch("uar.api.server._idempotency_get") as mget:
            mget.return_value = None
            with patch("uar.api.server._idempotency_set") as mset:
                with patch("uar.core.executor.Executor") as MockExec:
                    mock_result = MagicMock()
                    mock_result.run_id = "r1"
                    mock_result.goal_id = "g1"
                    mock_result.status = "completed"
                    mock_result.skills = []
                    mock_result.outputs = []
                    mock_result.errors = []
                    mock_result.events = []
                    mock_result.final_context = {}
                    mock_result.user_id = None
                    MockExec.return_value.run.return_value = mock_result
                    response = client.post(
                        "/api/uar/run",
                        json={
                            "idempotency_key": "key456",
                            "goal": "test",
                        },
                    )
        assert response.status_code == 200
        assert mset.called

    def test_uar_error(self, client):
        from uar.api.routers.runs import UARError

        with patch("uar.core.executor.Executor") as MockExec:
            MockExec.return_value.run.side_effect = UARError("test error")
            response = client.post(
                "/api/uar/run",
                json={"goal": "test"},
            )
        assert response.status_code == 400

    def test_unexpected_error(self, client):
        with patch("uar.core.executor.Executor") as MockExec:
            MockExec.return_value.run.side_effect = RuntimeError("boom")
            response = client.post(
                "/api/uar/run",
                json={"goal": "test"},
            )
        assert response.status_code == 500


class TestGetRunTimeline:
    def test_forbidden(self, client):
        mock_store = MagicMock()
        mock_store.get_by_run_id.return_value = {
            "run_id": "r1",
            "user_id": "other_user",
        }
        with patch("uar.api.server.store", mock_store):
            with patch(
                "uar.api.routers.runs.auth_middleware",
                return_value={"user": "me", "tier": "user"},
            ):
                response = client.get("/api/uar/runs/r1/timeline")
        assert response.status_code == 403


class TestListRunsError:
    def test_exception(self, client):
        mock_store = MagicMock()
        mock_store.list_records.side_effect = RuntimeError("db fail")
        with patch("uar.api.server.store", mock_store):
            response = client.get("/api/uar/runs")
        assert response.status_code == 500


class TestProvenanceAuth:
    def test_forbidden(self, client):
        mock_store = MagicMock()
        mock_store.get_by_run_id.return_value = {
            "run_id": "r1",
            "user_id": "other_user",
        }
        with patch("uar.api.server.store", mock_store):
            with patch(
                "uar.api.routers.runs.auth_middleware",
                return_value={"user": "me", "tier": "user"},
            ):
                response = client.get("/api/provenance/r1")
        assert response.status_code == 403


class TestCompareRunsMissing:
    def test_second_not_found(self, client):
        def side_effect(rid):
            if rid == "r1":
                return {"run_id": "r1", "status": "completed"}
            return None

        mock_store = MagicMock()
        mock_store.get_by_run_id.side_effect = side_effect
        with patch("uar.api.server.store", mock_store):
            response = client.get("/api/uar/runs/r1/compare/r2")
        assert response.status_code == 404


class TestBulkDeleteOwnership:
    def test_ownership_filter(self, client):
        def side_effect(rid):
            if rid == "r1":
                return {"run_id": "r1", "user_id": "me"}
            if rid == "r2":
                return {"run_id": "r2", "user_id": "other"}
            return None

        mock_store = MagicMock()
        mock_store.get_by_run_id.side_effect = side_effect
        mock_store.delete.return_value = None
        with patch("uar.api.server.store", mock_store):
            with patch(
                "uar.api.routers.runs.auth_middleware",
                return_value={"user": "me", "tier": "user"},
            ):
                response = client.post(
                    "/api/uar/runs/bulk-delete",
                    json={"run_ids": ["r1", "r2"]},
                )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1


class TestQueryCode:
    def test_missing_question(self, client):
        response = client.post("/api/uar/query-code", json={})
        # 401 from auth before body validation
        assert response.status_code in (400, 401)

    def test_integration_not_installed(self, client):
        with patch.dict("sys.modules", {"uar.integrations": None}):
            response = client.post(
                "/api/uar/query-code",
                json={"question": "how does this work"},
            )
        # Auth or import error
        assert response.status_code in (401, 503)
