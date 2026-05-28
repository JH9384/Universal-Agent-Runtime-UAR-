"""Tests for newly implemented skills: quantum_ml, math_plot_3d, code_analysis."""

from __future__ import annotations

import pytest

from uar.core.contracts import GoalSpec, PipelineContext


def _make_ctx(metadata: dict | None = None) -> PipelineContext:
    """Build a minimal PipelineContext for skill tests."""
    goal = GoalSpec(
        id="test-run",
        user_intent="test",
        objective="test",
        metadata=metadata or {},
    )
    ctx = PipelineContext(goal=goal)
    return ctx


# ---------------------------------------------------------------------------
# quantum_ml
# ---------------------------------------------------------------------------

class TestQuantumML:
    def test_missing_pennylane_returns_error(self):
        from uar.skills.quantum_ml import _check_pennylane, quantum_ml

        if _check_pennylane():
            pytest.skip(
                "PennyLane is installed — skipping missing-dependency test"
            )

        ctx = _make_ctx({"qml_task": "qnn_regression"})
        result = quantum_ml(ctx)
        assert result["status"] == "failed"
        assert "PennyLane not installed" in result["error"]

    def test_check_pennylane_is_boolean(self):
        from uar.skills.quantum_ml import _check_pennylane
        assert isinstance(_check_pennylane(), bool)


# ---------------------------------------------------------------------------
# math_plot_3d
# ---------------------------------------------------------------------------

class TestMathPlot3D:
    def test_missing_deps_returns_error(self):
        from uar.skills.math_plot_3d import _check_deps, math_plot_3d

        if _check_deps():
            pytest.skip(
                "matplotlib+numpy installed — skipping missing-dependency test"
            )

        ctx = _make_ctx({"plot_3d_type": "surface"})
        result = math_plot_3d(ctx)
        assert result["status"] == "failed"
        assert "matplotlib and numpy not installed" in result["error"]

    def test_check_deps_boolean(self):
        from uar.skills.math_plot_3d import _check_deps
        assert isinstance(_check_deps(), bool)

    def test_parse_range_defaults(self):
        from uar.skills.math_plot_3d import _parse_range
        assert _parse_range([-1, 1]) == (-1.0, 1.0)
        assert _parse_range("bad") == (-5.0, 5.0)
        assert _parse_range(None) == (-5.0, 5.0)

    def test_no_expression_uses_default(self):
        from uar.skills.math_plot_3d import math_plot_3d

        ctx = _make_ctx({"plot_3d_type": "surface"})
        result = math_plot_3d(ctx)
        if result["status"] == "failed" and "not installed" in result.get("error", ""):
            pytest.skip("matplotlib+numpy not installed")
        assert result["status"] == "completed"
        assert "image_base64" in result
        assert result["plot_type"] == "surface"

    def test_wireframe_type(self):
        from uar.skills.math_plot_3d import math_plot_3d

        ctx = _make_ctx({"plot_3d_type": "wireframe"})
        result = math_plot_3d(ctx)
        if result["status"] == "failed" and "not installed" in result.get("error", ""):
            pytest.skip("matplotlib+numpy not installed")
        assert result["status"] == "completed"
        assert result["plot_type"] == "wireframe"

    def test_parametric_curve_type(self):
        from uar.skills.math_plot_3d import math_plot_3d

        ctx = _make_ctx({
            "plot_3d_type": "parametric_curve",
            "plot_3d_parametric": {"x": "cos(t)", "y": "sin(t)", "z": "t"},
        })
        result = math_plot_3d(ctx)
        if result["status"] == "failed" and "not installed" in result.get("error", ""):
            pytest.skip("matplotlib+numpy not installed")
        assert result["status"] == "completed"
        assert result["plot_type"] == "parametric_curve"


# ---------------------------------------------------------------------------
# code_analysis
# ---------------------------------------------------------------------------

PYTHON_SAMPLE = """
import os
from typing import Dict

def greet(name: str) -> str:
    return f"Hello, {name}!"

class Greeter:
    def __init__(self, greeting: str):
        self.greeting = greeting

    def greet(self, name: str) -> str:
        return f"{self.greeting}, {name}!"

def main():
    g = Greeter("Hi")
    print(g.greet("world"))
    # TODO: add more languages

if __name__ == "__main__":
    main()
"""

GO_SAMPLE = """
package main

import "fmt"

func main() {
    fmt.Println("hello")
}

type Config struct {
    Name string
}
"""

RUST_SAMPLE = """
use std::io;

fn main() {
    println!("hello");
}

struct Point {
    x: i32,
    y: i32,
}

enum Color {
    Red,
    Green,
}
"""


class TestCodeAnalysis:
    def test_empty_source_fails(self):
        from uar.skills.code_analysis import code_analysis

        ctx = _make_ctx({"code_source": ""})
        result = code_analysis(ctx)
        assert result["status"] == "failed"
        assert "code_source is required" in result["error"]

    def test_python_detection_and_metrics(self):
        from uar.skills.code_analysis import code_analysis

        ctx = _make_ctx({"code_source": PYTHON_SAMPLE})
        result = code_analysis(ctx)
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "python"
        assert "greet" in res["functions"]
        assert "Greeter" in res["classes"]
        assert "os" in res["imports"]
        assert res["lines"]["total"] > 0
        assert res["complexity"]["function_count"] >= 2
        assert any(i["type"] == "todo" for i in res["issues"])

    def test_go_detection(self):
        from uar.skills.code_analysis import code_analysis

        ctx = _make_ctx({"code_source": GO_SAMPLE})
        result = code_analysis(ctx)
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "go"
        assert "main" in res["functions"]
        assert "Config" in res["classes"]  # structs are classes here
        assert "fmt" in res["imports"]

    def test_rust_detection(self):
        from uar.skills.code_analysis import code_analysis

        ctx = _make_ctx({"code_source": RUST_SAMPLE})
        result = code_analysis(ctx)
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "rust"
        assert "main" in res["functions"]
        assert "Point" in res["classes"]
        assert "Color" in res["classes"]
        assert "std::io" in res["imports"]

    def test_explicit_language_override(self):
        from uar.skills.code_analysis import code_analysis

        ctx = _make_ctx({"code_source": GO_SAMPLE, "code_language": "go"})
        result = code_analysis(ctx)
        assert result["status"] == "completed"
        assert result["result"]["language"] == "go"

    def test_long_line_issue(self):
        from uar.skills.code_analysis import code_analysis

        long_line = "x = " + "1" * 150
        source = f"def foo():\n    {long_line}\n"
        ctx = _make_ctx({"code_source": source})
        result = code_analysis(ctx)
        issues = result["result"]["issues"]
        assert any(i["type"] == "long_line" for i in issues)

    def test_bare_except_python(self):
        from uar.skills.code_analysis import code_analysis

        source = "try:\n    pass\nexcept:\n    pass\n"
        ctx = _make_ctx({"code_source": source, "code_language": "python"})
        result = code_analysis(ctx)
        issues = result["result"]["issues"]
        assert any(i["type"] == "bare_except" for i in issues)

    def test_inline_comments_counted(self):
        """Regression: inline comments were missed by _count_lines."""
        from uar.skills.code_analysis import code_analysis

        source = "x = 1  # inline comment\n"
        ctx = _make_ctx({"code_source": source, "code_language": "python"})
        result = code_analysis(ctx)
        lines = result["result"]["lines"]
        assert lines["total"] == 1
        assert lines["blank"] == 0
        assert lines["comment"] == 1
        assert lines["code"] == 0

    def test_block_comment_not_at_column_zero(self):
        """Regression: block comments starting mid-line were not detected."""
        from uar.skills.code_analysis import code_analysis

        source = 'int x = 1; /* block\ncomment */\n'
        ctx = _make_ctx({"code_source": source, "code_language": "c"})
        result = code_analysis(ctx)
        lines = result["result"]["lines"]
        assert lines["total"] == 2
        assert lines["comment"] == 2
        assert lines["code"] == 0

    def test_all_issues_have_line_field(self):
        """Regression: issue objects had inconsistent shapes."""
        from uar.skills.code_analysis import code_analysis

        source = (
            "def foo():\n"
            "    x = " + "1" * 150 + "  # TODO fix me\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            "        pass\n"
        )
        ctx = _make_ctx({"code_source": source, "code_language": "python"})
        result = code_analysis(ctx)
        issues = result["result"]["issues"]
        assert len(issues) > 0
        for issue in issues:
            assert "line" in issue, f"Issue {issue} missing 'line' field"
            assert isinstance(issue["line"], int)

    def test_todo_has_line_number(self):
        """Regression: _find_todos did not include line numbers."""
        from uar.skills.code_analysis import _find_todos

        source = "line1\nline2\n# TODO: fix this\nline4\n"
        todos = _find_todos(source)
        assert len(todos) == 1
        assert todos[0]["line"] == 3
        assert todos[0]["type"] == "TODO"

    def test_no_go_dead_code_issues(self):
        """Regression: Go section was a no-op and should not add noise issues."""
        from uar.skills.code_analysis import code_analysis

        source = "package main\n\nfunc main() {\n    println(\"hello\")\n}\n"
        ctx = _make_ctx({"code_source": source, "code_language": "go"})
        result = code_analysis(ctx)
        issues = result["result"]["issues"]
        # No Go-specific noise issues should be present
        assert all(i["type"] not in ("go_error_handling",) for i in issues)


# ---------------------------------------------------------------------------
# myhdl_design (pre-existing, verify it's registered)
# ---------------------------------------------------------------------------

class TestSkillRegistration:
    def test_skills_registered_in_registry(self):
        import uar.skills.myhdl_design  # noqa: F401
        from uar.core.registry import registry
        skills = registry.list()
        assert "quantum_ml" in skills
        assert "math_plot_3d" in skills
        assert "code_analysis" in skills
        assert "myhdl_design" in skills


class TestMyHDLDesign:
    def test_skill_exists_and_runs(self):
        from uar.skills.myhdl_design import myhdl_design

        ctx = _make_ctx({
            "source": (
                "from myhdl import Signal, intbv\n"
                "\n"
                "def my_module(clk):\n"
                "    pass"
            ),
            "module_name": "test_mod",
        })
        result = myhdl_design(ctx)
        assert result["status"] == "completed"
        assert result["result"]["module_name"] == "test_mod"
        assert "verilog_stub" in result["result"]
