from fastapi.testclient import TestClient
from uar.api.server import app

client = TestClient(app)


def test_path_outside_root_blocked():
    response = client.post(
        "/api/uar/run",
        json={
            "goal": "bad path",
            "skills": ["doc_ingest"],
            "input_path": "/tmp",
        },
    )
    # Path validation rejects absolute paths at the API level
    assert response.status_code == 400
    data = response.json()
    assert "error" in data["detail"]
    assert data["detail"]["field"] == "input_path"


def test_relative_escape_blocked():
    response = client.post(
        "/api/uar/run",
        json={
            "goal": "escape",
            "skills": ["doc_ingest"],
            "input_path": "../",
        },
    )
    # Path validation rejects relative escape attempts at the API level
    assert response.status_code == 400
    data = response.json()
    assert "error" in data["detail"]
    assert data["detail"]["field"] == "input_path"
