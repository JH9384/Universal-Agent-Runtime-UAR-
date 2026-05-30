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


def test_run_endpoint():
    response = client.post("/api/uar/run", json={"goal": "test"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_list_runs():
    response = client.get("/api/uar/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_recipes():
    """GET /api/uar/recipes returns canonical recipe definitions"""
    response = client.get("/api/uar/recipes")
    assert response.status_code == 200
    data = response.json()
    assert "recipes" in data
    assert isinstance(data["recipes"], list)
    ids = [r["id"] for r in data["recipes"]]
    assert "review" in ids
    assert "gr_query" in ids
    for recipe in data["recipes"]:
        assert "id" in recipe
        assert "label" in recipe
        assert "skills" in recipe
        assert isinstance(recipe["skills"], list)


def test_run_with_user_created_recipe():
    """User-created recipe sent in metadata is accepted and expanded"""
    payload = {
        "goal": "test user recipe",
        "execution_order": [
            {"type": "recipe", "content": "my_custom", "id": "r1"},
        ],
        "metadata": {
            "recipe_definitions": [
                {
                    "id": "my_custom",
                    "label": "My Custom",
                    "skills": ["doc_ingest"],
                    "hint": "",
                }
            ]
        },
    }
    response = client.post("/api/uar/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_run_with_unknown_user_recipe_raises():
    """Unknown user recipe without definition raises validation error"""
    payload = {
        "goal": "test unknown recipe",
        "execution_order": [
            {"type": "recipe", "content": "unknown_xyz", "id": "r1"},
        ],
    }
    response = client.post("/api/uar/run", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Invalid execution order" in str(data)


AUTH_HEADERS = {"Authorization": "Bearer dev-key-12345"}


def test_recipe_crud_lifecycle():
    """Full CRUD lifecycle for user recipes via API"""
    recipe = {
        "id": "test_crud",
        "label": "Test CRUD",
        "skills": ["doc_ingest"],
        "hint": "test",
    }

    # Create
    r = client.post("/api/uar/recipes", json=recipe, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["created"] == "test_crud"

    # Read (merged list, auth not required but shows user recipes when authed)
    r = client.get("/api/uar/recipes", headers=AUTH_HEADERS)
    assert r.status_code == 200
    ids = [rec["id"] for rec in r.json()["recipes"]]
    assert "test_crud" in ids

    # Update
    updated = {**recipe, "skills": ["sum_review"]}
    r = client.put(
        "/api/uar/recipes/test_crud", json=updated, headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["updated"] == "test_crud"

    # Delete
    r = client.delete("/api/uar/recipes/test_crud", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["deleted"] == "test_crud"

    # Verify gone
    r = client.get("/api/uar/recipes", headers=AUTH_HEADERS)
    ids = [rec["id"] for rec in r.json()["recipes"]]
    assert "test_crud" not in ids


def test_cannot_modify_canonical_recipe():
    """Canonical recipes are protected from modification/deletion"""
    recipe = {"id": "review", "label": "X", "skills": ["a"]}

    r = client.post("/api/uar/recipes", json=recipe, headers=AUTH_HEADERS)
    assert r.status_code == 409

    r = client.put(
        "/api/uar/recipes/review", json=recipe, headers=AUTH_HEADERS
    )
    assert r.status_code == 403

    r = client.delete("/api/uar/recipes/review", headers=AUTH_HEADERS)
    assert r.status_code == 403


def test_update_unknown_recipe_returns_404():
    """Updating a nonexistent recipe returns 404, not 500."""
    r = client.put(
        "/api/uar/recipes/does_not_exist",
        json={"id": "does_not_exist", "label": "X", "skills": ["a"]},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_found"


def test_update_recipe_wrong_owner_returns_403():
    """Updating another user's recipe returns 403."""
    from unittest.mock import patch

    with patch(
        "uar.api.server._recipe_svc.update",
        side_effect=PermissionError("Not owner"),
    ):
        r = client.put(
            "/api/uar/recipes/other_user_recipe",
            json={
                "id": "other_user_recipe",
                "label": "X",
                "skills": ["a"],
            },
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "forbidden"


def test_delete_unknown_recipe_returns_404():
    """Deleting a nonexistent recipe returns 404, not 500."""
    r = client.delete(
        "/api/uar/recipes/does_not_exist",
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_found"


def test_delete_recipe_wrong_owner_returns_403():
    """Deleting another user's recipe returns 403."""
    from unittest.mock import patch

    with patch(
        "uar.api.server._recipe_svc.delete",
        side_effect=PermissionError("Not owner"),
    ):
        r = client.delete(
            "/api/uar/recipes/other_user_recipe",
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "forbidden"


def test_create_recipe_invalid_skills_returns_400():
    """Recipe with 'skills must be' error returns 400."""
    from unittest.mock import patch

    with patch(
        "uar.api.server._recipe_svc.create",
        side_effect=ValueError("Skills must be a list"),
    ):
        r = client.post(
            "/api/uar/recipes",
            json={"id": "bad_skills", "label": "X", "skills": "not_list"},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_skills"


def test_create_recipe_unexpected_error_returns_500():
    """Unexpected recipe service error returns 500."""
    from unittest.mock import patch

    with patch(
        "uar.api.server._recipe_svc.create",
        side_effect=ValueError("something broke"),
    ):
        r = client.post(
            "/api/uar/recipes",
            json={"id": "boom", "label": "X", "skills": ["a"]},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 500
    assert r.json()["detail"]["error"] == "internal"


def test_create_recipe_non_string_id_returns_400():
    """Recipe id that is not a string returns 400."""
    r = client.post(
        "/api/uar/recipes",
        json={"id": 123, "label": "X", "skills": ["a"]},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "missing_id"


def test_unexpected_exception_not_masked_by_recipe_handler():
    """Programming errors (AttributeError etc.) must NOT be caught by the
    domain exception handler — they should propagate uncaught so we know
    something is actually broken."""
    from unittest.mock import patch

    with patch(
        "uar.api.server._recipe_svc.update",
        side_effect=AttributeError("'NoneType' object has no attribute 'x'"),
    ):
        with pytest.raises(AttributeError):
            client.put(
                "/api/uar/recipes/some_recipe",
                json={"id": "some_recipe", "label": "X", "skills": ["a"]},
                headers=AUTH_HEADERS,
            )


class TestHierarchicalExecutionIntegration:
    """End-to-end integration tests for hierarchical recipe execution."""

    def test_run_with_use_hierarchical_executes_recipe(self):
        """use_hierarchical flag triggers recipe boundary events."""
        payload = {
            "goal": "test hierarchical",
            "execution_order": [
                {"type": "recipe", "content": "gr_query", "id": "r1"},
            ],
            "use_hierarchical": True,
        }
        response = client.post("/api/uar/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        events = data.get("events", [])
        types = [e["type"] for e in events]
        assert "recipe_start" in types
        assert "recipe_end" in types

    def test_stream_with_hierarchical_emits_boundary_events(self):
        """Streaming with use_hierarchical emits recipe_start/end."""
        import json as _json

        with client.stream(
            "POST",
            "/api/uar/stream",
            json={
                "goal": "stream hierarchical",
                "execution_order": [
                    {"type": "recipe", "content": "gr_query", "id": "r1"},
                ],
                "use_hierarchical": True,
            },
        ) as response:
            assert response.status_code == 200
            events = []
            for chunk in response.iter_text():
                if not chunk:
                    continue
                for frame in chunk.strip().split("\n\n"):
                    lines = frame.splitlines()
                    data_lines = [
                        line.removeprefix("data: ")
                        for line in lines
                        if line.startswith("data: ")
                    ]
                    if data_lines:
                        events.append(_json.loads("".join(data_lines)))

        types = [e["type"] for e in events]
        assert "recipe_start" in types
        assert "recipe_end" in types
        assert "skill_start" in types
        assert "skill_complete" in types

    def test_recipe_timeout_override_via_api(self):
        """Recipe with timeout field is respected end-to-end."""
        payload = {
            "goal": "test timeout override",
            "execution_order": [
                {
                    "type": "recipe",
                    "content": "custom_timeout",
                    "id": "r1",
                },
            ],
            "metadata": {
                "recipe_definitions": [
                    {
                        "id": "custom_timeout",
                        "label": "Custom",
                        "skills": ["section_sum"],
                        "timeout": 0.5,
                    }
                ]
            },
        }
        response = client.post("/api/uar/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"


class TestEcosystemAPI:
    """End-to-end tests for UOR ecosystem API endpoints."""

    def test_ecosystem_status_endpoint(self):
        """GET /ecosystem/status returns all integration statuses."""
        response = client.get(
            "/ecosystem/status", headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        integrations = data["integrations"]
        assert "uor_addr" in integrations
        assert "hologram" in integrations
        assert "moltbook" in integrations
        assert "prism_btc" in integrations
        assert "severance_ai" in integrations
        assert "anunix" in integrations

    def test_run_ecosystem_skill_uor_addr_canonicalize(self):
        """Execute uor_addr_canonicalize skill via /api/uar/run."""
        payload = {
            "goal": "canonicalize test data",
            "skills": ["uor_addr_canonicalize"],
            "metadata": {"data": {"hello": "world"}},
        }
        response = client.post("/api/uar/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Skill results are nested in final_context
        skill_result = data["final_context"]["uor_addr_canonicalize"]
        assert skill_result["status"] == "completed"
        assert "envelope" in skill_result
        assert skill_result["envelope"]["digest"].startswith("sha256:")

    def test_run_ecosystem_skill_uor_ecosystem_status(self):
        """Execute uor_ecosystem_status skill via /api/uar/run."""
        payload = {
            "goal": "check ecosystem",
            "skills": ["uor_ecosystem_status"],
        }
        response = client.post("/api/uar/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Skill results are nested in final_context
        skill_result = data["final_context"]["uor_ecosystem_status"]
        assert skill_result["status"] == "completed"
        assert "integrations" in skill_result

    def test_stream_ecosystem_skill(self):
        """Streaming execution of ecosystem skill emits events."""
        import json as _json

        with client.stream(
            "POST",
            "/api/uar/stream",
            json={
                "goal": "stream ecosystem status",
                "skills": ["uor_ecosystem_status"],
            },
        ) as response:
            assert response.status_code == 200
            events = []
            for chunk in response.iter_text():
                if not chunk:
                    continue
                for frame in chunk.strip().split("\n\n"):
                    lines = frame.splitlines()
                    data_lines = [
                        line.removeprefix("data: ")
                        for line in lines
                        if line.startswith("data: ")
                    ]
                    if data_lines:
                        events.append(_json.loads("".join(data_lines)))

        types = [e["type"] for e in events]
        assert "skill_start" in types
        assert "skill_complete" in types
        assert "metrics" in types
