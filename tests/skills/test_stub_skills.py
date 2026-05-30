"""Tests for stub_skills module.

Covers the _make_stub factory.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.stub_skills import _make_stub


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestMakeStub:
    def test_available_package(self):
        stub = _make_stub("test_skill", "os")
        result = stub(_ctx({}))
        assert result["status"] == "completed"
        assert result["result"]["available"] is True
        assert "ready" in result["result"]["message"]

    def test_unavailable_package(self):
        stub = _make_stub("test_skill", "nonexistent_pkg_xyz")
        result = stub(_ctx({}))
        assert result["status"] == "completed"
        assert result["result"]["available"] is False
        assert "install" in result["result"]["message"]

    def test_no_package(self):
        stub = _make_stub("test_skill", "")
        result = stub(_ctx({}))
        assert result["status"] == "completed"
        assert result["result"]["available"] is True
        assert "ready" in result["result"]["message"]
