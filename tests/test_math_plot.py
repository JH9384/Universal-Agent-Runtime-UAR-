"""Unit tests for math_plot skill.

Covers: function plotting, parametric, polar, scatter, missing deps.
"""

from __future__ import annotations

import base64

import pytest

from uar.skills import math_plot
from uar.core.contracts import GoalSpec, PipelineContext


def _ctx(metadata: dict) -> PipelineContext:
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata=metadata,
    )
    return PipelineContext(goal=goal, data={})


class TestMathPlotMissingDeps:
    def test_missing_matplotlib(self):
        try:
            import matplotlib  # noqa: F401
            pytest.skip("matplotlib is installed")
        except ImportError:
            pass
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["sin(x)"],
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "failed"
        assert "matplotlib" in result["error"].lower()


class TestMathPlotWithMatplotlib:
    def setup_method(self):
        try:
            import matplotlib  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            pytest.skip("matplotlib or numpy not installed")

    def test_function_plot_single(self):
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["sin(x)"],
            "plot_x_range": [-6, 6],
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["plot_type"] == "function"
        assert "image_base64" in result
        # Verify it's valid base64
        img = base64.b64decode(result["image_base64"])
        assert img[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic

    def test_function_plot_multiple(self):
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["sin(x)", "cos(x)", "x**2 / 10"],
            "plot_x_range": [-5, 5],
            "plot_title": "Trig + Parabola",
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["expressions"] == ["sin(x)", "cos(x)", "x**2 / 10"]
        assert "image_base64" in result

    def test_parametric_plot(self):
        ctx = _ctx({
            "plot_type": "parametric",
            "plot_parametric": {
                "x": "sin(3*t)",
                "y": "cos(2*t)",
                "t_range": [0, 6.28318],
            },
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["plot_type"] == "parametric"
        assert "image_base64" in result

    def test_polar_plot(self):
        ctx = _ctx({
            "plot_type": "polar",
            "plot_polar": {
                "r": "1 + cos(theta)",
                "theta_range": [0, 6.28318],
            },
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["plot_type"] == "polar"
        assert "image_base64" in result

    def test_scatter_plot(self):
        ctx = _ctx({
            "plot_type": "scatter",
            "plot_scatter_data": [[0, 0], [1, 2], [2, 4], [3, 9]],
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["plot_type"] == "scatter"
        assert result["point_count"] == 4
        assert "image_base64" in result

    def test_function_plot_y_range(self):
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["x**3"],
            "plot_x_range": [-2, 2],
            "plot_y_range": [-10, 10],
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert result["y_range"] == [-2.0, 2.0]

    def test_dark_style(self):
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["exp(-x**2)"],
            "plot_x_range": [-3, 3],
            "plot_style": "dark_background",
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert "image_base64" in result

    def test_invalid_expression_graceful(self):
        ctx = _ctx({
            "plot_type": "function",
            "plot_expressions": ["invalid!!!"],
            "plot_x_range": [-1, 1],
        })
        result = math_plot.math_plot(ctx)
        assert result["status"] == "completed"
        assert "image_base64" in result
