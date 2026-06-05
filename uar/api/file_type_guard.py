"""File type whitelist enforcement for UAR uploads.

Operators can restrict allowed file extensions and MIME types via:
    UAR_FILE_TYPE_WHITELIST — comma-separated extensions (e.g. .pdf,.txt)
    UAR_FILE_TYPE_BLOCKLIST  — comma-separated extensions to always reject
"""

from __future__ import annotations

import logging
import os
from typing import FrozenSet, Optional

logger = logging.getLogger(__name__)

# Default extensions allowed for document library uploads
_DEFAULT_ALLOWED = frozenset(
    {
        ".pdf",
        ".docx",
        ".xlsx",
        ".xlsm",
        ".ipynb",
        ".parquet",
        ".feather",
        ".txt",
        ".md",
        ".rst",
        ".tex",
        ".bib",
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".html",
        ".htm",
        ".xml",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".r",
        ".jl",
        ".rmd",
        ".qmd",
    }
)

# Always dangerous — never allowed regardless of whitelist
_DEFAULT_BLOCKLIST = frozenset(
    {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".sh",
        ".app",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        ".msi",
        ".com",
        ".scr",
        ".pif",
        ".vbs",
        ".jar",
        ".war",
        ".ear",
    }
)


def _load_env_set(name: str, default: FrozenSet[str]) -> FrozenSet[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


_ALLOWED_EXTS = _load_env_set("UAR_FILE_TYPE_WHITELIST", _DEFAULT_ALLOWED)
_BLOCKED_EXTS = _load_env_set("UAR_FILE_TYPE_BLOCKLIST", _DEFAULT_BLOCKLIST)


def get_allowed_extensions() -> FrozenSet[str]:
    """Return the current allowed extension set."""
    return _ALLOWED_EXTS


def get_blocked_extensions() -> FrozenSet[str]:
    """Return the current blocklist extension set."""
    return _BLOCKED_EXTS


def check_file_type(
    filename: str,
    content_type: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Check if a file passes the type whitelist.

    Returns:
        (allowed, reason) — reason is None when allowed.
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext in _BLOCKED_EXTS:
        return False, f"Extension '{ext}' is blocked"

    if _ALLOWED_EXTS and ext not in _ALLOWED_EXTS:
        return False, f"Extension '{ext}' not in whitelist"

    # Basic MIME type sanity check
    if content_type:
        blocked_mime_prefixes = (
            "application/x-ms",
            "application/x-dosexec",
            "application/x-executable",
        )
        for prefix in blocked_mime_prefixes:
            if content_type.startswith(prefix):
                return False, f"MIME type '{content_type}' is blocked"

    return True, None
