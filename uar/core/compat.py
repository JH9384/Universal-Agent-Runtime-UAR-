"""Compatibility utilities for optional dependencies.

Provides helpers for lazy imports, safe module loading, and graceful
degradation when optional packages are not installed.
"""

from __future__ import annotations

import importlib
from typing import Any, Optional


def lazy_import(module: str) -> Optional[Any]:
    """Return the named module if installed, otherwise None.

    Eliminates the repeated try/except ImportError pattern across skills:

        mod = lazy_import("autonomi")
        if mod is None:
            return {"status": "failed", "error": "Package not installed"}

    Args:
        module: Fully-qualified module name (e.g. ``"autonomi"``).

    Returns:
        The imported module, or ``None`` if it is not available.
    """
    try:
        return importlib.import_module(module)
    except ImportError:
        return None
