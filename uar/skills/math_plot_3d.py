"""3D mathematical plotting skill using matplotlib.

Generates 3D surface, wireframe, and parametric curve plots,
returning base64-encoded PNG images for frontend rendering.

Environment Variables:
    MATH_PLOT_DPI - DPI for generated plots (default: 150)
    MATH_PLOT_FIGSIZE - Figure size in inches as "w,h"
        (default: "8,6")

Goal Metadata:
    plot_3d_type - Type: 'surface', 'wireframe', 'parametric_curve',
                   'parametric_surface', 'contour3d'
    plot_3d_expression - z = f(x, y) expression (for surface/wireframe)
    plot_3d_x_range - [min, max] for x-axis (default: [-5, 5])
    plot_3d_y_range - [min, max] for y-axis (default: [-5, 5])
    plot_3d_parametric - {x: expr, y: expr, z: expr, t_range: [min, max]}
                         (for parametric curve)
    plot_3d_u_range - [min, max] for u parameter (default: [0, 2*pi])
    plot_3d_v_range - [min, max] for v parameter (default: [0, 2*pi])
    plot_3d_title - Optional plot title
    plot_3d_style - Matplotlib style: 'default', 'dark_background'
    plot_3d_elev - Elevation angle for view (default: 30)
    plot_3d_azim - Azimuth angle for view (default: -60)
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Any, Dict, Optional, Tuple

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.safe_eval import safe_eval

logger = logging.getLogger(__name__)

DEFAULT_DPI = max(
    1,
    min(600, int(os.getenv("MATH_PLOT_DPI", "150").strip() or "150")),
)
_figsize_raw = os.getenv("MATH_PLOT_FIGSIZE", "8,6").strip() or "8,6"
_figsize_parts = [p.strip() for p in _figsize_raw.split(",") if p.strip()]
try:
    DEFAULT_FIGSIZE = tuple(float(x) for x in _figsize_parts[:2])
except (ValueError, TypeError):
    DEFAULT_FIGSIZE = (8.0, 6.0)


def _check_deps() -> bool:
    import importlib.util
    return (
        importlib.util.find_spec("matplotlib") is not None
        and importlib.util.find_spec("numpy") is not None
    )


def _encode_figure(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DEFAULT_DPI, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _parse_range(range_val) -> Tuple[float, float]:
    if isinstance(range_val, (list, tuple)) and len(range_val) >= 2:
        return float(range_val[0]), float(range_val[1])
    return -5.0, 5.0


def _plot_surface(
    expr: str,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    title: Optional[str] = None,
    style: str = "default",
    elev: float = 30.0,
    azim: float = -60.0,
) -> Dict[str, Any]:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig = plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)

    x = np.linspace(x_range[0], x_range[1], 100)
    y = np.linspace(y_range[0], y_range[1], 100)
    X, Y = np.meshgrid(x, y)

    expr_clean = expr.replace("^", "**")
    safe_dict = {
        "np": np, "x": X, "y": Y,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
        "pi": np.pi, "e": np.e, "abs": np.abs,
    }

    try:
        Z = safe_eval(expr_clean, safe_dict)
        ax.plot_surface(X, Y, Z, cmap="viridis", alpha=0.8, edgecolor="none")
    except Exception:
        logger.exception("3D surface evaluation failed")
        ax.text2D(
            0.5, 0.5, f"Error: {expr}",
            transform=ax.transAxes, color="red",
        )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    if title:
        ax.set_title(title)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "surface",
        "expression": expr,
        "x_range": list(x_range),
        "y_range": list(y_range),
    }


def _plot_wireframe(
    expr: str,
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    title: Optional[str] = None,
    style: str = "default",
    elev: float = 30.0,
    azim: float = -60.0,
) -> Dict[str, Any]:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig = plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)

    x = np.linspace(x_range[0], x_range[1], 50)
    y = np.linspace(y_range[0], y_range[1], 50)
    X, Y = np.meshgrid(x, y)

    expr_clean = expr.replace("^", "**")
    safe_dict = {
        "np": np, "x": X, "y": Y,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
        "pi": np.pi, "e": np.e, "abs": np.abs,
    }

    try:
        Z = safe_eval(expr_clean, safe_dict)
        ax.plot_wireframe(
            X, Y, Z, rstride=2, cstride=2,
            color="blue", alpha=0.6,
        )
    except Exception:
        logger.exception("3D wireframe evaluation failed")
        ax.text2D(
            0.5, 0.5, f"Error: {expr}",
            transform=ax.transAxes, color="red",
        )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    if title:
        ax.set_title(title)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "wireframe",
        "expression": expr,
        "x_range": list(x_range),
        "y_range": list(y_range),
    }


def _plot_parametric_3d(
    x_expr: str,
    y_expr: str,
    z_expr: str,
    t_range: Tuple[float, float],
    title: Optional[str] = None,
    style: str = "default",
    elev: float = 30.0,
    azim: float = -60.0,
) -> Dict[str, Any]:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    matplotlib.use("Agg")
    plt.style.use(style)

    fig = plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)

    t = np.linspace(t_range[0], t_range[1], 1000)
    x_expr_c = x_expr.replace("^", "**")
    y_expr_c = y_expr.replace("^", "**")
    z_expr_c = z_expr.replace("^", "**")

    safe_dict = {
        "t": t, "np": np,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
        "pi": np.pi, "e": np.e, "abs": np.abs,
    }

    try:
        x = safe_eval(x_expr_c, safe_dict)
        y = safe_eval(y_expr_c, safe_dict)
        z = safe_eval(z_expr_c, safe_dict)
        ax.plot(x, y, z, color="#3b82f6", linewidth=2)
    except Exception:
        logger.exception("3D parametric plot failed")
        ax.text2D(0.5, 0.5, "Error", transform=ax.transAxes, color="red")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    if title:
        ax.set_title(title)

    img_b64 = _encode_figure(fig)
    plt.close(fig)

    return {
        "success": True,
        "image_base64": img_b64,
        "format": "png",
        "plot_type": "parametric_curve",
        "x_expression": x_expr,
        "y_expression": y_expr,
        "z_expression": z_expr,
        "t_range": list(t_range),
    }


@register_skill("math_plot_3d")
def math_plot_3d(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate 3D mathematical plots as base64 PNG images.

    Supports surface plots, wireframes, and 3D parametric curves.
    """
    if not _check_deps():
        return {
            "status": "failed",
            "error": (
                "matplotlib and numpy not installed. "
                "Install with: pip install matplotlib numpy"
            ),
            "plot_type": "unavailable",
        }

    params = ctx.goal.metadata or {}
    plot_type = str(params.get("plot_3d_type", "surface")).lower()
    title = params.get("plot_3d_title") or None
    style = str(params.get("plot_3d_style", "default"))
    elev = float(params.get("plot_3d_elev", 30.0))
    azim = float(params.get("plot_3d_azim", -60.0))

    try:
        if plot_type == "wireframe":
            expr = str(
                params.get("plot_3d_expression", "sin(sqrt(x**2 + y**2))")
            )
            x_range = _parse_range(params.get("plot_3d_x_range", [-5, 5]))
            y_range = _parse_range(params.get("plot_3d_y_range", [-5, 5]))
            result = _plot_wireframe(
                expr, x_range, y_range,
                title=title, style=style,
                elev=elev, azim=azim,
            )
        elif plot_type == "parametric_curve":
            param = params.get("plot_3d_parametric", {})
            x_expr = str(param.get("x", "cos(t)"))
            y_expr = str(param.get("y", "sin(t)"))
            z_expr = str(param.get("z", "t"))
            t_range = _parse_range(param.get("t_range", [0, 6.28318]))
            result = _plot_parametric_3d(
                x_expr, y_expr, z_expr, t_range,
                title=title, style=style,
                elev=elev, azim=azim,
            )
        else:
            # Default: surface
            expr = str(
                params.get("plot_3d_expression", "sin(sqrt(x**2 + y**2))")
            )
            x_range = _parse_range(params.get("plot_3d_x_range", [-5, 5]))
            y_range = _parse_range(params.get("plot_3d_y_range", [-5, 5]))
            result = _plot_surface(
                expr, x_range, y_range, title=title, style=style,
                elev=elev, azim=azim,
            )

        result["status"] = "completed" if result.get("success") else "failed"
        return result

    except Exception:
        logger.exception("math_plot_3d failed")
        return {
            "status": "failed",
            "error": "3D plot generation failed",
            "plot_type": plot_type,
        }
