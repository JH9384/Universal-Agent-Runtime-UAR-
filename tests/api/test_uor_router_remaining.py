"""Tests for uar.api.routers.uor remaining coverage gaps."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.routers.uor import router, get_store


@pytest.fixture
def client():
    app = FastAPI()
    mock_store = MagicMock()
    mock_store.get_object.return_value = {
        "digest": "sha256:test", "attributes": {}
    }
    mock_store.list_runtimes.return_value = {"py": "sha256:py"}
    mock_store.get_runtime_digest.return_value = "sha256:py"
    mock_store.get_content.return_value = {
        "content_bytes": b"hello",
        "media_type": "text/plain",
    }
    mock_store.get_lineage.return_value = []
    app.dependency_overrides[get_store] = lambda: mock_store
    app.include_router(router)
    return TestClient(app)


class TestObjectContent:
    def test_post_content(self, client):
        response = client.post(
            "/objects/sha256:test/content",
            files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
        )
        assert response.status_code == 200
        assert response.json()["size"] == 4

    def test_post_content_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_object.side_effect = KeyError("missing")
        app = FastAPI()
        app.dependency_overrides[get_store] = lambda: mock_store
        app.include_router(router)
        c = TestClient(app)
        response = c.post(
            "/objects/sha256:nope/content",
            files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
        )
        assert response.status_code == 404

    def test_download(self, client):
        response = client.get("/objects/sha256:test/download")
        assert response.status_code == 200
        assert response.content == b"hello"

    def test_download_no_content(self, client):
        mock_store = MagicMock()
        mock_store.get_object.return_value = {
            "digest": "sha256:test", "attributes": {}
        }
        mock_store.get_content.return_value = None
        app = FastAPI()
        app.dependency_overrides[get_store] = lambda: mock_store
        app.include_router(router)
        c = TestClient(app)
        response = c.get("/objects/sha256:test/download")
        assert response.status_code == 404


class TestRuntimeRegister:
    def test_register(self, client):
        with patch("uar.api.routers.uor.register_runtime_object") as mock_reg:
            mock_reg.return_value = {
                "digest": "sha256:rt",
                "created_at": "2024-01-01",
            }
            response = client.post(
                "/runtimes/register",
                json={
                    "name": "test-rt",
                    "code": "print(1)",
                    "description": "test",
                    "tags": [],
                    "attributes": {},
                },
            )
        assert response.status_code == 200
        assert response.json()["name"] == "test-rt"

    def test_register_sandbox_error(self, client):
        from uar.objects import SandboxError
        with patch("uar.api.routers.uor.register_runtime_object") as mock_reg:
            mock_reg.side_effect = SandboxError("bad code")
            response = client.post(
                "/runtimes/register",
                json={
                    "name": "test-rt",
                    "code": "bad",
                    "description": "test",
                    "tags": [],
                    "attributes": {},
                },
            )
        assert response.status_code == 400


class TestComposer:
    def test_compose(self, client):
        with patch("uar.api.routers.uor.create_record") as mock_create:
            mock_create.return_value = {
                "digest": "sha256:new",
                "created_at": "2024-01-01",
            }
            response = client.post(
                "/agents/composer/compose",
                json={
                    "inputs": ["sha256:a"],
                    "compositionType": "collection",
                    "attributes": {},
                },
            )
        assert response.status_code == 200
        assert "created" in response.json()


class TestExecution:
    def test_run(self, client):
        with patch("uar.api.routers.uor.execute_runtime") as mock_exec:
            mock_exec.return_value = {"status": "completed"}
            response = client.post(
                "/agents/execution/run",
                json={
                    "runtimeName": "py",
                    "runtimeObject": "sha256:py",
                    "inputs": [],
                    "parameters": {},
                },
            )
        assert response.status_code == 200

    def test_run_not_found(self, client):
        with patch("uar.api.routers.uor.execute_runtime") as mock_exec:
            mock_exec.side_effect = KeyError("missing")
            response = client.post(
                "/agents/execution/run",
                json={
                    "runtimeName": "py",
                    "runtimeObject": "sha256:py",
                    "inputs": [],
                    "parameters": {},
                },
            )
        assert response.status_code == 404

    def test_run_timeout(self, client):
        from uar.objects import SandboxError
        with patch("uar.api.routers.uor.execute_runtime") as mock_exec:
            mock_exec.side_effect = SandboxError("timed out")
            response = client.post(
                "/agents/execution/run",
                json={
                    "runtimeName": "py",
                    "runtimeObject": "sha256:py",
                    "inputs": [],
                    "parameters": {},
                },
            )
        assert response.status_code == 408

    def test_run_sandbox_error(self, client):
        from uar.objects import SandboxError
        with patch("uar.api.routers.uor.execute_runtime") as mock_exec:
            mock_exec.side_effect = SandboxError("bad code")
            response = client.post(
                "/agents/execution/run",
                json={
                    "runtimeName": "py",
                    "runtimeObject": "sha256:py",
                    "inputs": [],
                    "parameters": {},
                },
            )
        assert response.status_code == 400


class TestWorkflow:
    def test_run(self, client):
        with patch("uar.api.routers.uor.workflow_run") as mock_wf:
            mock_wf.return_value = {"status": "completed"}
            response = client.post(
                "/workflows/run",
                json={
                    "name": "wf",
                    "inputs": [],
                    "steps": [{"parameters": {}}],
                },
            )
        assert response.status_code == 200

    def test_run_not_found(self, client):
        with patch("uar.api.routers.uor.workflow_run") as mock_wf:
            mock_wf.side_effect = KeyError("missing")
            response = client.post(
                "/agents/workflow/run",
                json={
                    "name": "wf",
                    "inputs": [],
                    "steps": [{"parameters": {}}],
                },
            )
        assert response.status_code == 404

    def test_run_timeout(self, client):
        from uar.objects import SandboxError
        with patch("uar.api.routers.uor.workflow_run") as mock_wf:
            mock_wf.side_effect = SandboxError("timed out")
            response = client.post(
                "/workflows/run",
                json={
                    "name": "wf",
                    "inputs": [],
                    "steps": [{"parameters": {}}],
                },
            )
        assert response.status_code == 408


class TestConstraint:
    def test_check(self, client):
        with patch(
            "uar.api.routers.uor.svc_constraint_check"
        ) as mock_check:
            mock_check.return_value = {"allowed": True}
            response = client.post(
                "/agents/constraint/check",
                json={
                    "agent": "a",
                    "action": "read",
                    "target": "t",
                },
            )
        assert response.status_code == 200

    def test_check_not_found(self, client):
        with patch(
            "uar.api.routers.uor.svc_constraint_check"
        ) as mock_check:
            mock_check.side_effect = KeyError("missing")
            response = client.post(
                "/agents/constraint/check",
                json={
                    "agent": "a",
                    "action": "read",
                    "target": "t",
                },
            )
        assert response.status_code == 404


class TestBridge:
    def test_ingest(self, client):
        with patch(
            "uar.api.routers.uor.svc_bridge_ingest"
        ) as mock_ingest:
            mock_ingest.return_value = {"ingested": 1}
            response = client.post(
                "/agents/bridge/ingest",
                json={
                    "source": {"uri": "s"},
                    "normalize": True,
                    "attributes": {},
                },
            )
        assert response.status_code == 200


class TestInference:
    def test_analyze(self, client):
        with patch(
            "uar.api.routers.uor.svc_inference_analyze"
        ) as mock_analyze:
            mock_analyze.return_value = {"result": "ok"}
            response = client.post(
                "/agents/inference/analyze",
                json={"objects": ["sha256:a"], "task": "t"},
            )
        assert response.status_code == 200

    def test_analyze_not_found(self, client):
        with patch(
            "uar.api.routers.uor.svc_inference_analyze"
        ) as mock_analyze:
            mock_analyze.side_effect = KeyError("missing")
            response = client.post(
                "/agents/inference/analyze",
                json={"objects": ["sha256:a"], "task": "t"},
            )
        assert response.status_code == 404


class TestDelegation:
    def test_plan(self, client):
        with patch(
            "uar.api.routers.uor.svc_delegation_plan"
        ) as mock_plan:
            mock_plan.return_value = {"plan": []}
            response = client.post(
                "/agents/delegation/plan",
                json={
                    "goal": "g",
                    "inputs": [],
                    "allowedAgents": [],
                },
            )
        assert response.status_code == 200

    def test_plan_not_found(self, client):
        with patch(
            "uar.api.routers.uor.svc_delegation_plan"
        ) as mock_plan:
            mock_plan.side_effect = KeyError("missing")
            response = client.post(
                "/agents/delegation/plan",
                json={
                    "goal": "g",
                    "inputs": [],
                    "allowedAgents": [],
                },
            )
        assert response.status_code == 404


class TestVerifierMismatch:
    def test_verify_mismatch(self, client):
        response = client.post(
            "/agents/verifier/verify",
            json={
                "object": "sha256:test",
                "expectedDigest": "sha256:other",
            },
        )
        assert response.status_code == 200
        assert response.json()["verified"] is False
        assert "digest-mismatch" in response.json()["notes"]
