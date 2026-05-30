"""Tests for Verilator simulation skill.

Covers _check_verilator and verilator_sim.
"""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.verilator_sim import _check_verilator, verilator_sim


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestCheckVerilator:
    """Verilator availability check."""

    def test_not_installed(self):
        with patch("shutil.which", return_value=None):
            result = _check_verilator()
        assert result["available"] is False
        assert result["version"] == "unknown"

    def test_installed(self):
        with patch("shutil.which", return_value="/usr/bin/verilator"):
            mock_proc = type("P", (), {"stdout": "Verilator 5.008"})()
            with patch("subprocess.run", return_value=mock_proc):
                result = _check_verilator()
        assert result["available"] is True
        assert result["version"] == "5.008"

    def test_version_check_fails(self):
        with patch("shutil.which", return_value="/usr/bin/verilator"):
            with patch("subprocess.run", side_effect=OSError):
                result = _check_verilator()
        assert result["available"] is True
        assert result["version"] == "unknown"


class TestVerilatorSim:
    """Skill entry point."""

    def test_no_source(self):
        with patch("uar.skills.verilator_sim._check_verilator") as mock:
            mock.return_value = {
                "available": True, "version": "5.0"
            }
            result = verilator_sim(_ctx({"source": ""}))
        assert result["status"] == "completed"
        assert result["result"]["source_length"] == 0
        assert result["result"]["lint_issues"] == []

    def test_lint_issues(self):
        with patch("uar.skills.verilator_sim._check_verilator") as mock:
            mock.return_value = {
                "available": True, "version": "5.0"
            }
            result = verilator_sim(
                _ctx({"source": "module test (\n"})
            )
        assert result["status"] == "completed"
        assert len(result["result"]["lint_issues"]) > 0
        issues = result["result"]["lint_issues"]
        assert any("parentheses" in i.lower() for i in issues)

    def test_valid_source(self):
        with patch("uar.skills.verilator_sim._check_verilator") as mock:
            mock.return_value = {
                "available": True, "version": "5.0"
            }
            result = verilator_sim(
                _ctx({"source": "module test(); endmodule"})
            )
        assert result["status"] == "completed"
        assert result["result"]["lint_issues"] == []

    def test_no_module_declaration(self):
        with patch("uar.skills.verilator_sim._check_verilator") as mock:
            mock.return_value = {
                "available": True, "version": "5.0"
            }
            result = verilator_sim(_ctx({"source": "assign a = b;"}))
        assert "module" in result["result"]["lint_issues"][0].lower()

    def test_mismatched_braces(self):
        with patch("uar.skills.verilator_sim._check_verilator") as mock:
            mock.return_value = {
                "available": True, "version": "5.0"
            }
            result = verilator_sim(_ctx({"source": "module test(); {"}))
        issues = result["result"]["lint_issues"]
        assert any("braces" in i.lower() for i in issues)
