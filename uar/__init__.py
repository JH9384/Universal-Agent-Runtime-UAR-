"""Universal Agent Runtime (UAR).

Python core runtime for modular, goal-driven agent execution.
"""

from pathlib import Path

__all__ = ["__version__"]

_ROOT = Path(__file__).resolve().parent
_VERSION_FILE = _ROOT.parent / "VERSION"

if _VERSION_FILE.exists():
    __version__ = _VERSION_FILE.read_text().strip()
else:
    __version__ = "unknown"
