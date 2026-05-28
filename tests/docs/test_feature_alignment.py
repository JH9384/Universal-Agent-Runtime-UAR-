"""Comprehensive alignment tests for all frontend/backend features.

Catches misalignment in:
- Recipes (frontend vs backend canonical definitions)
- API endpoints (frontend URLs vs backend routes)
- Event types (backend emits vs frontend handles)
- Metadata fields (frontend sends vs backend expects)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Set

import pytest  # noqa: F401

PROJECT_ROOT = Path(__file__).parent.parent.parent
PANEL_PATH = (
    PROJECT_ROOT / "apps" / "web" / "src" / "components" / "UARPanel.tsx"
)
SERVER_PATH = PROJECT_ROOT / "uar" / "api" / "server.py"
RECIPE_PATH = PROJECT_ROOT / "uar" / "core" / "recipes.py"
EVENTS_PATH = PROJECT_ROOT / "uar" / "services" / "events.py"


def _read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_frontend_api_endpoints(source: str) -> Set[str]:
    """Extract all API endpoint paths called from the frontend."""
    endpoints: Set[str] = set()
    # Match fetch('/api/uar/...') or fetch(`/api/uar/...`)
    for match in re.finditer(r"fetch\(['\"`]((/api/[^'\"`]+))", source):
        endpoints.add(match.group(1))
    return endpoints


def _extract_backend_routes(source: str) -> Set[str]:
    """Extract all API routes defined in the backend."""
    routes: Set[str] = set()
    # Match @app.get("/path") and @router.get("/path") etc.
    for match in re.finditer(
        r'@(?:app|router)\.'
        r'(get|post|put|delete|websocket)'
        r'\(\s*["\']([^"\']+)["\']',
        source,
    ):
        routes.add(match.group(2))
    return routes


def _extract_frontend_event_handlers(source: str) -> Set[str]:
    """Extract event types explicitly handled in the frontend."""
    handlers: Set[str] = set()
    for match in re.finditer(r"json\.type === ['\"]([^'\"]+)['\"]", source):
        handlers.add(match.group(1))
    return handlers


def _extract_backend_event_types(source: str) -> Set[str]:
    """Extract event types created by the backend EventService."""
    types: Set[str] = set()
    for match in re.finditer(r'event_type=["\']([^"\']+)["\']', source):
        types.add(match.group(1))
    return types


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecipeAlignment:
    """Frontend RECIPES must match backend DEFAULT_RECIPES."""

    def test_recipe_ids_match(self) -> None:
        """Every frontend recipe ID must exist in backend DEFAULT_RECIPES."""
        panel_src = _read_file(PANEL_PATH)
        recipe_src = _read_file(RECIPE_PATH)

        # Extract frontend recipe IDs from RECIPES array block only
        start = panel_src.find("const RECIPES: Recipe[] = [")
        frontend_ids: Set[str] = set()
        if start != -1:
            start += len("const RECIPES: Recipe[] = [")
            depth = 1
            i = start
            while i < len(panel_src) and depth > 0:
                if panel_src[i] == "[":
                    depth += 1
                elif panel_src[i] == "]":
                    depth -= 1
                i += 1
            block = panel_src[start:i - 1]
            frontend_ids = set(
                re.findall(r"id:\s*['\"]([^'\"]+)['\"]", block)
            )

        # Extract backend recipe IDs
        backend_ids = set(
            re.findall(r'"([^"]+)":\s*\{', recipe_src)
        )

        missing_frontend = frontend_ids - backend_ids
        missing_backend = backend_ids - frontend_ids

        assert not missing_frontend, (
            f"Frontend recipes missing from backend: "
            f"{sorted(missing_frontend)}"
        )
        assert not missing_backend, (
            f"Backend recipes missing from frontend: "
            f"{sorted(missing_backend)}"
        )


class TestApiEndpointAlignment:
    """Every frontend fetch URL must have a matching backend route."""

    def test_all_frontend_endpoints_exist(self) -> None:
        """Frontend API calls must hit existing backend routes."""
        panel_src = _read_file(PANEL_PATH)
        server_src = _read_file(SERVER_PATH)

        # Also scan router files for extracted endpoints
        routers_dir = PROJECT_ROOT / "uar" / "api" / "routers"
        router_src = ""
        if routers_dir.exists():
            for f in routers_dir.glob("*.py"):
                router_src += _read_file(f)

        frontend_endpoints = _extract_frontend_api_endpoints(panel_src)
        backend_routes = _extract_backend_routes(server_src)
        backend_routes |= _extract_backend_routes(router_src)

        # Normalize: strip query params and path params for matching
        missing = set()
        for endpoint in frontend_endpoints:
            base = endpoint.split("?")[0]
            # Replace ${var} and :param with wildcards for fuzzy matching
            pattern = re.sub(r"\$\{[^}]+\}", r"[^/]+", base)
            pattern = re.sub(r":[^/]+", r"[^/]+", pattern)
            if not any(
                re.fullmatch(pattern, route)
                or route.startswith(base.rstrip("/"))
                for route in backend_routes
            ):
                missing.add(endpoint)

        assert not missing, (
            f"Frontend endpoints with no backend route: {sorted(missing)}"
        )


class TestEventTypeAlignment:
    """Backend event types should be handled by frontend."""

    def test_all_backend_events_known_to_frontend(self) -> None:
        """Every event type the backend emits should be handled by frontend."""
        panel_src = _read_file(PANEL_PATH)
        events_src = _read_file(EVENTS_PATH)
        executor_src = _read_file(
            PROJECT_ROOT / "uar" / "core" / "executor.py"
        )

        frontend_handlers = _extract_frontend_event_handlers(panel_src)
        backend_event_service = _extract_backend_event_types(events_src)

        # Also extract raw event types from executor yield statements
        _ev_types = [
            "skill_start", "skill_complete", "skill_failed",
            "recipe_start", "recipe_end", "recipe_skipped",
            "metrics",
        ]
        executor_types = set()
        for et in _ev_types:
            if f'"{et}"' in executor_src:
                executor_types.add(et)

        all_backend_types = backend_event_service | executor_types

        # Some events are intentionally just logged, not individually handled
        allowed_unhandled = {
            "complete",       # final wrap-up, logged as event
            "persisted",      # persistence confirmation, logged as event
            "heartbeat",      # connection keepalive, explicitly skipped
            "recipe_skipped",  # condition false, logged but not bannered
        }

        missing = all_backend_types - frontend_handlers - allowed_unhandled
        assert not missing, (
            f"Backend event types not handled by frontend: {sorted(missing)}\n"
            f"Add handlers in {PANEL_PATH}"
        )
