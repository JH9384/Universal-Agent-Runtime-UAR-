from __future__ import annotations

from pathlib import Path


def load_context(base: str | Path = ".") -> str:
    base = Path(base)
    for name in ["UAR_CONTEXT.md", "AGENTS.md", "CONTEXT.md"]:
        path = base / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""
