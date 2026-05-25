"""UAR package version helpers."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


@lru_cache(maxsize=1)
def get_uar_version() -> str:
    if not VERSION_FILE.exists():
        return "unknown"
    return VERSION_FILE.read_text().strip() or "unknown"
