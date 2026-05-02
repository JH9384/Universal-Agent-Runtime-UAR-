from fastapi.testclient import TestClient

from uar.api.server import app

client = TestClient(app)


def test_run_endpoint():
    response = client.post("/api/uar/run", json={"goal": "test"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_v1_run_endpoint_alias():
    response = client.post("/api/v1/uar/run", json={"goal": "test", "skills": ["section_sum"]})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["events"][0]["type"] == "start"


def test_list_runs():
    response = client.get("/api/uar/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_v1_list_runs_alias():
    response = client.get("/api/v1/uar/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
