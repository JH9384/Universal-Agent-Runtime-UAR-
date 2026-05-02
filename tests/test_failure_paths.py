from fastapi.testclient import TestClient

from uar.api.server import app
from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor
import uar.skills.section_sum  # noqa: F401

client = TestClient(app)


def test_executor_reports_missing_skill_failure():
    goal = GoalSpec(id="missing-skill", user_intent="missing", objective="missing")
    strategy = StrategySpec(goal_id=goal.id, ordered_skills=["not_a_real_skill"])

    result = Executor().run(strategy, goal)

    assert result.status == "failed"
    assert result.errors


def test_doc_ingest_bad_input_path_still_completes_with_warning():
    response = client.post(
        "/api/uar/run",
        json={
            "goal": "ingest missing path",
            "skills": ["doc_ingest"],
            "input_path": "./definitely-not-a-real-path",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "warning" in data["final_context"]["doc_ingest"]


def test_api_missing_goal_returns_validation_error():
    response = client.post("/api/uar/run", json={})
    assert response.status_code == 422
