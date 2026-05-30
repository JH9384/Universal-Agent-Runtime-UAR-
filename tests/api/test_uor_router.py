"""Tests for uar.api.routers.uor."""

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


class TestAgents:
    def test_list_agents(self, client):
        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data


class TestEcosystem:
    def test_status(self, client):
        with patch("uar.core.uor_ecosystem.get_uor_ecosystem") as mock_eco:
            mock_eco.return_value.status.return_value = {}
            response = client.get("/ecosystem/status")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestObjects:
    def test_post_object(self, client):
        response = client.post("/objects", json={})
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            assert "digest" in response.json()

    def test_get_object(self, client):
        response = client.get("/objects?digest=sha256:test")
        assert response.status_code == 200
        assert response.json()["digest"] == "sha256:test"

    def test_get_object_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_object.side_effect = KeyError("missing")
        app = FastAPI()
        app.dependency_overrides[get_store] = lambda: mock_store
        app.include_router(router)
        c = TestClient(app)
        response = c.get("/objects?digest=sha256:nope")
        assert response.status_code == 404


class TestRuntimes:
    def test_list_runtimes(self, client):
        response = client.get("/runtimes")
        assert response.status_code == 200
        assert "runtimes" in response.json()

    def test_get_runtime(self, client):
        response = client.get("/runtimes/py")
        assert response.status_code == 200
        assert response.json()["name"] == "py"

    def test_get_runtime_not_found(self, client):
        mock_store = MagicMock()
        mock_store.get_runtime_digest.return_value = None
        app = FastAPI()
        app.dependency_overrides[get_store] = lambda: mock_store
        app.include_router(router)
        c = TestClient(app)
        response = c.get("/runtimes/nope")
        assert response.status_code == 404

    def test_seed_runtimes(self, client):
        with patch("uar.objects.seed_standard_runtimes") as mock_seed:
            mock_seed.return_value = {}
            response = client.post("/runtimes/seed")
        assert response.status_code == 200


class TestVerifier:
    def test_verify(self, client):
        response = client.post(
            "/agents/verifier/verify",
            json={"object": "sha256:test", "expectedDigest": "sha256:test"},
        )
        assert response.status_code == 200
        assert response.json()["verified"] is True

    def test_compare(self, client):
        response = client.post(
            "/agents/verifier/compare",
            json={"left": "sha256:a", "right": "sha256:b"},
        )
        assert response.status_code == 200
        assert "equivalent" in response.json()


class TestLocator:
    def test_query(self, client):
        with patch("uar.api.routers.uor.svc_locator_query") as mock_q:
            mock_q.return_value = []
            response = client.post(
                "/agents/locator/query",
                json={"where": {}, "limit": 10},
            )
        assert response.status_code == 200
        assert "matches" in response.json()


class TestLineage:
    def test_trace(self, client):
        response = client.get("/agents/lineage/trace?digest=sha256:test")
        assert response.status_code == 200
        assert "events" in response.json()


class TestALM:
    def test_analyze(self, client):
        with patch(
            "uar.objects.alm_client.AtomicLanguageModelSkill"
        ) as mock_skill:
            mock_skill.return_value.analyze_grammar.return_value = {"ok": True}
            response = client.post(
                "/agents/atomic_lang_model/analyze",
                json={"grammar_spec": "test"},
            )
        assert response.status_code == 200

    def test_generate(self, client):
        with patch(
            "uar.objects.alm_client.AtomicLanguageModelSkill"
        ) as mock_skill:
            mock_skill.return_value.generate_sequence.return_value = ["a"]
            response = client.post(
                "/agents/atomic_lang_model/generate",
                json={"prefix": "a", "count": 1},
            )
        assert response.status_code == 200
        assert "generated" in response.json()

    def test_verify(self, client):
        with patch(
            "uar.objects.alm_client.AtomicLanguageModelSkill"
        ) as mock_skill:
            mock_skill.return_value.verify_syntax.return_value = {"ok": True}
            response = client.post(
                "/agents/atomic_lang_model/verify",
                json={"text": "hello"},
            )
        assert response.status_code == 200
