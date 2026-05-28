"""Tests for MicroPython embedded skill.

Covers _simulate_execution and micropython entry point.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.micropython import _simulate_execution, micropython


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestSimulateExecution:
    """MicroPython code simulation."""

    def test_empty_code(self):
        result = _simulate_execution("")
        assert result["stdout"] == []
        assert result["pins"] == {}
        assert result["errors"] == []

    def test_comments_ignored(self):
        result = _simulate_execution("# comment\n  \n")
        assert result["stdout"] == []

    def test_pin_init(self):
        code = "led = machine.Pin(2, machine.Pin.OUT)"
        result = _simulate_execution(code)
        assert "GPIO2" in result["pins"]
        assert result["pins"]["GPIO2"]["mode"] == "OUT"
        assert any("GPIO2" in s for s in result["stdout"])

    def test_pin_write(self):
        code = "led = machine.Pin(2, machine.Pin.OUT)\nled.value(1)"
        result = _simulate_execution(code)
        assert result["pins"]["led"]["value"] == 1
        assert any("set to 1" in s for s in result["stdout"])

    def test_print(self):
        code = 'print("hello world")'
        result = _simulate_execution(code)
        assert any("print" in s for s in result["stdout"])

    def test_pin_init_in(self):
        code = "btn = machine.Pin(0, machine.Pin.IN)"
        result = _simulate_execution(code)
        assert result["pins"]["GPIO0"]["mode"] == "IN"


class TestMicropythonSkill:
    """Skill entry point."""

    def test_empty_code(self):
        result = micropython(_ctx({"code": ""}))
        assert result["status"] == "failed"
        assert "required" in result["error"].lower()

    def test_basic_execution(self):
        result = micropython(_ctx({"code": "print(1)"}))
        assert result["status"] == "completed"
        assert "stdout" in result["result"]
        assert result["metrics"]["lines"] == 1

    def test_metrics(self):
        code = "led = machine.Pin(2, machine.Pin.OUT)\nled.value(1)"
        result = micropython(_ctx({"code": code}))
        assert result["status"] == "completed"
        assert result["metrics"]["pins"] == 2  # GPIO2 + led
        assert result["metrics"]["outputs"] > 0
