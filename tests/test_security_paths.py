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
    data = response.json()
    assert "error" in data["final_context"]["doc_ingest"]


def test_relative_escape_blocked():
    response = client.post(
        "/api/uar/run",
        json={
            "goal": "escape",
            "skills": ["doc_ingest"],
            "input_path": "../",
        },
    )
    data = response.json()
    assert "error" in data["final_context"]["doc_ingest"]
