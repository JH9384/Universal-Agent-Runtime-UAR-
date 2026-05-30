"""Tests for math_plot_3d skill.

Covers surface, wireframe, parametric curve plots, view angles,
style options, error handling, and missing dependencies.
"""

import base64

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills import math_plot_3d as mp3d


def _ctx(metadata: dict) -> PipelineContext:
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata=metadata,
    )
    return PipelineContext(goal=goal, data={})


def _decode_png(result: dict) -> bytes:
    return base64.b64decode(result["image_base64"])


class TestMathPlot3DSurface:
    """3D surface plots."""

    def test_surface_default_expression(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
        }))
        assert result["status"] == "completed"
        assert result["plot_type"] == "surface"
        assert "image_base64" in result
        img = _decode_png(result)
        assert img[:8] == b"\x89PNG\r\n\x1a\n"

    def test_surface_custom_expression(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_expression": "x**2 + y**2",
            "plot_3d_x_range": [-2, 2],
            "plot_3d_y_range": [-2, 2],
        }))
        assert result["status"] == "completed"
        assert result["expression"] == "x**2 + y**2"

    def test_surface_with_title(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_expression": "sin(x)*cos(y)",
            "plot_3d_title": "Wave Surface",
        }))
        assert result["status"] == "completed"

    def test_surface_invalid_expression_graceful(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_expression": "invalid!!!",
        }))
        assert result["status"] == "completed"
        assert "image_base64" in result


class TestMathPlot3DWireframe:
    """3D wireframe plots."""

    def test_wireframe_basic(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "wireframe",
            "plot_3d_expression": "sin(sqrt(x**2 + y**2))",
        }))
        assert result["status"] == "completed"
        assert result["plot_type"] == "wireframe"
        assert "image_base64" in result

    def test_wireframe_custom_range(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "wireframe",
            "plot_3d_expression": "x*y",
            "plot_3d_x_range": [-1, 1],
            "plot_3d_y_range": [-1, 1],
        }))
        assert result["status"] == "completed"
        assert result["x_range"] == [-1.0, 1.0]


class TestMathPlot3DParametric:
    """3D parametric curve plots."""

    def test_parametric_curve_helix(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "parametric_curve",
            "plot_3d_parametric": {
                "x": "cos(t)",
                "y": "sin(t)",
                "z": "t",
                "t_range": [0, 6.28318],
            },
        }))
        assert result["status"] == "completed"
        assert result["plot_type"] == "parametric_curve"
        assert "image_base64" in result

    def test_parametric_curve_custom_range(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "parametric_curve",
            "plot_3d_parametric": {
                "x": "t",
                "y": "t**2",
                "z": "t**3",
                "t_range": [-1, 1],
            },
        }))
        assert result["status"] == "completed"
        assert result["t_range"] == [-1.0, 1.0]


class TestMathPlot3DViewAndStyle:
    """Camera angles and matplotlib styles."""

    def test_custom_elevation_azimuth(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_elev": 45.0,
            "plot_3d_azim": 90.0,
        }))
        assert result["status"] == "completed"
        assert "image_base64" in result

    def test_dark_style(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_style": "dark_background",
        }))
        assert result["status"] == "completed"
        assert "image_base64" in result

    def test_default_style(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "surface",
            "plot_3d_style": "default",
        }))
        assert result["status"] == "completed"


class TestMathPlot3DEdgeCases:
    """Edge cases and error handling."""

    def test_missing_dependencies(self):
        from unittest import mock

        def _mock_find_spec(name):
            if name in ("matplotlib", "numpy"):
                return None
            return __import__("importlib.util").find_spec(name)

        with mock.patch("importlib.util.find_spec", _mock_find_spec):
            result = mp3d.math_plot_3d(_ctx({
                "plot_3d_type": "surface",
            }))
            assert result["status"] == "failed"
            assert "matplotlib" in result["error"].lower()

    def test_empty_metadata_defaults(self):
        result = mp3d.math_plot_3d(_ctx({}))
        assert result["status"] == "completed"
        assert result["plot_type"] == "surface"

    def test_partial_parametric_missing_keys(self):
        """Parametric with missing keys uses defaults."""
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "parametric_curve",
            "plot_3d_parametric": {},
        }))
        assert result["status"] == "completed"
        assert result["plot_type"] == "parametric_curve"

    def test_range_parsing(self):
        """_parse_range handles various input types."""
        assert mp3d._parse_range([0, 5]) == (0.0, 5.0)
        assert mp3d._parse_range((-1, 1)) == (-1.0, 1.0)
        assert mp3d._parse_range(None) == (-5.0, 5.0)
        # Single-element list falls through to default
        assert mp3d._parse_range([1]) == (-5.0, 5.0)

    def test_invalid_figsize_env(self):
        import subprocess
        import sys
        code = (
            "import os; os.environ['MATH_PLOT_FIGSIZE'] = 'bad'; "
            "import uar.skills.math_plot_3d as m; "
            "print(m.DEFAULT_FIGSIZE)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "(8.0, 6.0)" in result.stdout

    def test_wireframe_with_title(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "wireframe",
            "plot_3d_expression": "x*y",
            "plot_3d_title": "Wire Test",
        }))
        assert result["status"] == "completed"

    def test_wireframe_eval_error(self):
        from unittest.mock import patch
        with patch(
            "uar.skills.math_plot_3d.safe_eval",
            side_effect=ValueError("bad"),
        ):
            result = mp3d.math_plot_3d(_ctx({
                "plot_3d_type": "wireframe",
                "plot_3d_expression": "x*y",
            }))
        assert result["status"] == "completed"
        assert "image_base64" in result

    def test_parametric_with_title(self):
        result = mp3d.math_plot_3d(_ctx({
            "plot_3d_type": "parametric_curve",
            "plot_3d_parametric": {"x": "t", "y": "t", "z": "t"},
            "plot_3d_title": "Param Test",
        }))
        assert result["status"] == "completed"

    def test_parametric_eval_error(self):
        from unittest.mock import patch
        with patch(
            "uar.skills.math_plot_3d.safe_eval",
            side_effect=ValueError("bad"),
        ):
            result = mp3d.math_plot_3d(_ctx({
                "plot_3d_type": "parametric_curve",
                "plot_3d_parametric": {"x": "t", "y": "t", "z": "t"},
            }))
        assert result["status"] == "completed"
        assert "image_base64" in result
