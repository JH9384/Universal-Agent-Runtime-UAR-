"""Mathematical plotting skill using matplotlib.

Generates 2D plots of mathematical functions and parametric curves,
returning base64-encoded PNG images for frontend rendering.

Environment Variables:
    MATH_PLOT_DPI - DPI for generated plots (default: 150)
    MATH_PLOT_FIGSIZE - Figure size in inches as "w,h"
        (default: "8,6")

Goal Metadata:
    plot_type - Type: 'function', 'parametric', 'polar', 'scatter'
    plot_expressions - List of expressions to plot (for function type)
    plot_x_range - [min, max] range for x-axis (default: [-10, 10])
    plot_y_range - Optional [min, max] range for y-axis
    plot_parametric - {x: expr, y: expr, t_range: [min, max]}
    plot_polar - {r: expr, theta_range: [min, max]}
    plot_title - Optional plot title
    plot_x_label - Optional x-axis label
    plot_y_label - Optional y-axis label
    plot_style - Matplotlib style: 'default', 'dark_background', 'seaborn'
    plot_grid - Show grid: true/false (default: true)
    plot_legend - Show legend: true/false (default: true)
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.safe_eval import safe_eval

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_DPI = max(
    1, int(os.getenv("MATH_PLOT_DPI", "150").strip() or "150")
)
_figsize_raw = os.getenv("MATH_PLOT_FIGSIZE", "8,6").strip() or "8,6"
_figsize_parts = [p.strip() for p in _figsize_raw.split(",") if p.strip()]
try:
    DEFAULT_FIGSIZE = tuple(float(x) for x in _figsize_parts[:2])
except (ValueError, TypeError):
    DEFAULT_FIGSIZE = (8.0, 6.0)


def _check_matplotlib_available() -> bool:
    """Check if matplotlib and numpy are available."""
    import importlib.util

    return (
        importlib.util.find_spec("matplotlib") is not None
        and importlib.util.find_spec("numpy") is not None
    )


def _encode_figure(fig) -> str:
    """Encode matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DEFAULT_DPI, bbox_inches="tight")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_b64


def _parse_range(range_val) -> Tuple[float, float]:
    """Parse a range value into (min, max) tuple."""
    if isinstance(range_val, (list, tuple)) and len(range_val) >= 2:
        return float(range_val[0]), float(range_val[1])
    return -10.0, 10.0


def _plot_function(
    expressions: List[str],
    x_range: Tuple[float, float],
    y_range: Optional[Tuple[float, float]] = None,
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    style: str = "default",
    grid: bool = True,
    legend: bool = True,
) -> Dict[str, Any]:
    """Plot one or more 2D functions."""
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")  # Non-interactive backend
    plt.style.use(style)

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    x = np.linspace(x_range[0], x_range[1], 1000)
    colors = getattr(plt.cm, "tab10")(np.linspace(0, 1, max(len(expressions), 1)))

    for idx, expr in enumerate(expressions):
        expr = expr.strip()
        if not expr:
            continue
        # Convert common math notation
        expr = expr.replace("^", "**")
        try:
            y = safe_eval(
                expr,
                {
                    "x": x, "np": np, "sin": np.sin,
                    "cos": np.cos, "tan": np.tan,
                    "exp": np.exp, "log": np.log,
                    "log10": np.log10, "sqrt": np.sqrt,
                    "pi": np.pi, "e": np.e, "abs": np.abs,
                },
            )
            label = expr.replace("**", "^")
            ax.plot(x, y, color=colors[idx], linewidth=2, label=label)
        except Exception as exc:
            logger.warning(f"Failed to evaluate expression '{expr}': {exc}")
            ax.text(
                0.5, 0.5 - idx * 0.1, f"Error: {expr}",
                transform=ax.transAxes, color="red",
            )

    if legend and len(expressions) > 0:
        ax.legend(loc="best", framealpha=0.9)
    if grid:
        ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title)
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)
    ax.set_xlim(x_range)
    if y_range:
        ax.set_ylim(y_range)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "function",
        "expressions": expressions,
        "x_range": list(x_range),
        "y_range": list(y_range) if y_range else None,
    }


def _plot_parametric(
    x_expr: str,
    y_expr: str,
    t_range: Tuple[float, float],
    title: Optional[str] = None,
    style: str = "default",
    grid: bool = True,
) -> Dict[str, Any]:
    """Plot a parametric curve."""
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    t = np.linspace(t_range[0], t_range[1], 2000)
    x_expr = x_expr.replace("^", "**")
    y_expr = y_expr.replace("^", "**")

    safe_dict = {
        "t": t, "np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "sqrt": np.sqrt, "pi": np.pi, "e": np.e,
        "abs": np.abs,
    }

    try:
        x = safe_eval(x_expr, safe_dict)
        y = safe_eval(y_expr, safe_dict)
        ax.plot(x, y, color="#3b82f6", linewidth=2)
    except Exception as exc:
        logger.warning(f"Parametric plot failed: {exc}")
        ax.text(0.5, 0.5, f"Error: {exc}", transform=ax.transAxes, color="red")

    if grid:
        ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")
    if title:
        ax.set_title(title)
    ax.set_xlabel("x(t)")
    ax.set_ylabel("y(t)")

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "parametric",
        "x_expression": x_expr,
        "y_expression": y_expr,
        "t_range": list(t_range),
    }


def _plot_polar(
    r_expr: str,
    theta_range: Tuple[float, float],
    title: Optional[str] = None,
    style: str = "default",
    grid: bool = True,
) -> Dict[str, Any]:
    """Plot a polar curve."""
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig = plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = fig.add_subplot(111, projection="polar")

    theta = np.linspace(theta_range[0], theta_range[1], 2000)
    r_expr = r_expr.replace("^", "**")

    safe_dict = {
        "theta": theta, "np": np, "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "sqrt": np.sqrt, "pi": np.pi, "e": np.e,
        "abs": np.abs,
    }

    try:
        r = safe_eval(r_expr, safe_dict)
        ax.plot(theta, r, color="#10b981", linewidth=2)
    except Exception as exc:
        logger.warning(f"Polar plot failed: {exc}")
        ax.text(0.5, 0.5, f"Error: {exc}", transform=ax.transAxes, color="red")

    if grid:
        ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title, pad=20)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "polar",
        "r_expression": r_expr,
        "theta_range": list(theta_range),
    }


def _plot_scatter(
    points: List[List[float]],
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    style: str = "default",
    grid: bool = True,
) -> Dict[str, Any]:
    """Plot a scatter plot from data points."""
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    if len(points) > 0:
        xs = [p[0] for p in points if len(p) >= 2]
        ys = [p[1] for p in points if len(p) >= 2]
        colors = getattr(plt.cm, "viridis")(np.linspace(0, 1, len(xs)))
        ax.scatter(
            xs, ys, c=colors, s=50, alpha=0.7,
            edgecolors="white", linewidth=0.5,
        )
    else:
        ax.text(
            0.5, 0.5, "No data points",
            transform=ax.transAxes, ha="center",
        )

    if grid:
        ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title)
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "scatter",
        "point_count": len(points),
    }


@register_skill("math_plot")
def math_plot(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate 2D mathematical plots as base64 PNG images.

    Supports function plotting, parametric curves, polar plots,
    and scatter plots. Uses matplotlib with graceful degradation
    when not installed.

    Goal metadata:
        plot_type - 'function', 'parametric', 'polar', 'scatter'
        plot_expressions - List of y=f(x) expressions for function type
        plot_x_range - [min, max] for x-axis (default: [-10, 10])
        plot_y_range - Optional [min, max] for y-axis
        plot_parametric - {x: expr, y: expr, t_range: [min, max]}
        plot_polar - {r: expr, theta_range: [min, max]}
        plot_scatter_data - List of [x, y] points
        plot_title - Optional title
        plot_x_label - Optional x-axis label
        plot_y_label - Optional y-axis label
        plot_style - 'default', 'dark_background', 'seaborn'
        plot_grid - true/false (default: true)
        plot_legend - true/false (default: true)

    Returns:
        Dictionary with base64-encoded PNG image and metadata.
    """
    if not _check_matplotlib_available():
        return {
            "status": "failed",
            "error": (
                "matplotlib and numpy not installed. "
                "Install with: pip install matplotlib numpy"
            ),
            "plot_type": "unavailable",
        }

    params = ctx.goal.metadata or {}
    plot_type = str(params.get("plot_type", "function")).lower()
    title = params.get("plot_title") or None
    x_label = params.get("plot_x_label") or None
    y_label = params.get("plot_y_label") or None
    style = str(params.get("plot_style", "default"))
    grid = bool(params.get("plot_grid", True))
    legend = bool(params.get("plot_legend", True))

    try:
        if plot_type == "parametric":
            param = params.get("plot_parametric", {})
            x_expr = str(param.get("x", "sin(t)"))
            y_expr = str(param.get("y", "cos(t)"))
            t_range = _parse_range(param.get("t_range", [0, 2 * 3.14159]))
            result = _plot_parametric(
                x_expr, y_expr, t_range, title=title, style=style, grid=grid
            )
        elif plot_type == "polar":
            polar = params.get("plot_polar", {})
            r_expr = str(polar.get("r", "1 + cos(theta)"))
            theta_range = _parse_range(
                polar.get("theta_range", [0, 2 * 3.14159])
            )
            result = _plot_polar(
                r_expr, theta_range, title=title, style=style, grid=grid
            )
        elif plot_type == "scatter":
            points = params.get("plot_scatter_data", [])
            result = _plot_scatter(
                points, title=title, x_label=x_label, y_label=y_label,
                style=style, grid=grid,
            )
        else:
            # Default: function plotting
            expressions = params.get("plot_expressions", [])
            if isinstance(expressions, str):
                expressions = [expressions]
            if not expressions:
                expressions = ["sin(x)", "cos(x)"]
            x_range = _parse_range(params.get("plot_x_range", [-10, 10]))
            y_range = None
            if params.get("plot_y_range"):
                y_range = _parse_range(params["plot_y_range"])
            result = _plot_function(
                expressions, x_range, y_range=y_range,
                title=title, x_label=x_label, y_label=y_label,
                style=style, grid=grid, legend=legend,
            )

        result["status"] = "completed" if result.get("success") else "failed"
        return result

    except Exception as exc:
        logger.warning(f"math_plot failed: {exc}")
        return {"status": "failed", "error": str(exc), "plot_type": plot_type}
