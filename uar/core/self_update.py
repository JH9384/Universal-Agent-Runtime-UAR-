"""UAR self-update checker.

Checks the installed version against the latest available version
from PyPI (or git tags if PyPI is unavailable) and reports update
availability.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class UpdateStatus:
    """Current update availability status."""

    current_version: str = "unknown"
    latest_version: str = "unknown"
    update_available: bool = False
    source: str = "unknown"  # 'pypi' | 'git' | 'file'
    last_checked_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "update_available": self.update_available,
            "source": self.source,
            "last_checked_at": self.last_checked_at,
            "error": self.error,
        }


def _get_current_version() -> str:
    """Read the current UAR version from VERSION file."""
    from uar.version import get_uar_version

    return get_uar_version()


def _get_latest_from_pypi() -> Tuple[Optional[str], Optional[str]]:
    """Return (version, error) from PyPI JSON API."""
    import urllib.request
    import json

    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/universal-agent-runtime/json",
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            info = data.get("info", {})
            return info.get("version"), None
    except Exception as exc:
        return None, str(exc)


def _get_latest_from_git() -> Tuple[Optional[str], Optional[str]]:
    """Return (version, error) from latest git tag."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip("v"), None
        return None, result.stderr.strip() or "No git tags found"
    except Exception as exc:
        return None, str(exc)


def check_for_update() -> UpdateStatus:
    """Check whether a newer UAR version is available."""
    current = _get_current_version()
    status = UpdateStatus(
        current_version=current,
        last_checked_at=time.time(),
    )

    # Try PyPI first
    latest, err = _get_latest_from_pypi()
    if latest:
        status.latest_version = latest
        status.source = "pypi"
        status.update_available = _version_lt(current, latest)
        return status

    # Fallback to git tags
    latest, err2 = _get_latest_from_git()
    if latest:
        status.latest_version = latest
        status.source = "git"
        status.update_available = _version_lt(current, latest)
        return status

    status.error = err or err2 or "Unable to determine latest version"
    return status


def _version_lt(a: str, b: str) -> bool:
    """Compare two version strings (simple semantic versioning)."""
    try:
        from packaging.version import parse as parse_version

        return parse_version(a) < parse_version(b)
    except Exception:
        pass

    # Fallback: simple tuple comparison
    def _to_tuple(v: str) -> Tuple[int, ...]:
        parts = v.replace("-", ".").replace("_", ".").split(".")
        result: list[int] = []
        for p in parts:
            try:
                result.append(int(p))
            except ValueError:
                break
        return tuple(result)

    return _to_tuple(a) < _to_tuple(b)
