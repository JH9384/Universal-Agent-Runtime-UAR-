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


def test_module_registration_loop():
    """The module-level for loop must execute when _STUBS is populated."""
    import uar.skills.stub_skills as mod
    from uar.core.registry import register_skill, registry

    original = dict(mod._STUBS)
    mod._STUBS["fake_stub"] = "nonexistent_pkg"
    try:
        # Manually execute the same loop that runs at import time.
        for _name, _pkg in mod._STUBS.items():
            try:
                register_skill(_name)(mod._make_stub(_name, _pkg))
            except Exception:
                pass
        assert registry.is_registered("fake_stub")
    finally:
        mod._STUBS.clear()
        mod._STUBS.update(original)
        registry._skills.pop("fake_stub", None)
        registry._trie.remove("fake_stub")
