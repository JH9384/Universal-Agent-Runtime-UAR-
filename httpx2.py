"""Compatibility shim for environments expecting httpx2.

Starlette may try to import ``httpx2`` before falling back to ``httpx`` with a
deprecation warning. UAR still uses FastAPI/Starlette TestClient in tests, so
this shim keeps warning-clean CI collection stable while preserving existing
httpx behavior.
"""

import httpx as _httpx
from httpx import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_httpx, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_httpx)))
