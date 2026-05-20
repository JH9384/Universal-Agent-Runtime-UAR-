from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


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
    assert "unknown_xyz" in str(data)


def test_recipe_crud_lifecycle():
    """Full CRUD lifecycle for user recipes via API"""
    recipe = {
        "id": "test_crud",
        "label": "Test CRUD",
        "skills": ["doc_ingest"],
        "hint": "test",
    }

    # Create
    r = client.post("/api/uar/recipes", json=recipe)
    assert r.status_code == 200
    assert r.json()["created"] == "test_crud"

    # Read (merged list)
    r = client.get("/api/uar/recipes")
    assert r.status_code == 200
    ids = [rec["id"] for rec in r.json()["recipes"]]
    assert "test_crud" in ids

    # Update
    updated = {**recipe, "skills": ["sum_review"]}
    r = client.put("/api/uar/recipes/test_crud", json=updated)
    assert r.status_code == 200
    assert r.json()["updated"] == "test_crud"

    # Delete
    r = client.delete("/api/uar/recipes/test_crud")
    assert r.status_code == 200
    assert r.json()["deleted"] == "test_crud"

    # Verify gone
    r = client.get("/api/uar/recipes")
    ids = [rec["id"] for rec in r.json()["recipes"]]
    assert "test_crud" not in ids


def test_cannot_modify_canonical_recipe():
    """Canonical recipes are protected from modification/deletion"""
    recipe = {"id": "review", "label": "X", "skills": ["a"]}

    r = client.post("/api/uar/recipes", json=recipe)
    assert r.status_code == 409

    r = client.put("/api/uar/recipes/review", json=recipe)
    assert r.status_code == 403

    r = client.delete("/api/uar/recipes/review")
    assert r.status_code == 403
