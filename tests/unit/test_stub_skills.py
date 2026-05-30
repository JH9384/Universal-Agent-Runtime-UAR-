"""Tests for uar.skills.stub_skills."""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.stub_skills import _make_stub


def test_make_stub_available():
    """Stub with no required package must report available."""
    stub = _make_stub("test_skill", "")
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    result = stub(ctx)
    assert result["status"] == "completed"
    assert result["result"]["available"] is True
    assert "ready" in result["result"]["message"]


def test_make_stub_missing_package():
    """Stub with missing package must report unavailable."""
    stub = _make_stub("test_skill", "definitely_not_a_package_12345")
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    result = stub(ctx)
    assert result["status"] == "completed"
    assert result["result"]["available"] is False
    assert "install" in result["result"]["message"]
