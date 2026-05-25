"""Helpers for tracking the upstream UOR-Framework version."""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
UOR_VERSION_FILE = PACKAGE_ROOT / "third_party" / "uor" / "VERSION"


@lru_cache(maxsize=1)
def get_uor_version() -> str:
    """Return the recorded upstream UOR tag (e.g., ``v0.5.2``)."""
    if not UOR_VERSION_FILE.exists():
        return "unknown"
    return UOR_VERSION_FILE.read_text().strip() or "unknown"
