"""Shared utilities for matplotlib-based plotting skills.

Eliminates duplication between math_plot.py and math_plot_3d.py.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Tuple

# Configuration
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


def encode_figure(fig) -> str:
    """Encode a matplotlib figure to a base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DEFAULT_DPI, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def parse_range(
    range_val,
    default: Tuple[float, float] = (-10.0, 10.0),
) -> Tuple[float, float]:
    """Parse a range value into a (min, max) tuple."""
    if isinstance(range_val, (list, tuple)) and len(range_val) >= 2:
        return float(range_val[0]), float(range_val[1])
    return default
