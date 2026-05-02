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
