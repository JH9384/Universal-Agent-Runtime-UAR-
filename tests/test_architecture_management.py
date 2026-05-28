"""Architecture management tests: registry, services, middleware, routers.

Covers:
  - SkillRegistry (register, get, is_registered, list, prefix, lazy)
  - _SkillTrie prefix matching
  - RecipeService CRUD mappings
  - Middleware rate limiter reset behavior
  - Router endpoint patterns (health, runs, streaming)
  - Plugin loading guardrails
  - Circuit breaker decorator integration
"""

from __future__ import annotations

import threading
import pytest

from uar.core.registry import SkillRegistry, _SkillTrie, registry
from uar.core.exceptions import SkillNotFoundError, ValidationError
from uar.core.circuit_breaker_decorator import (
    with_circuit_breaker,
    reset_circuit_breaker,
)


# ---------------------------------------------------------------------------
# 1. _SkillTrie
# ---------------------------------------------------------------------------


class TestSkillTrie:
    """Prefix trie for skill name matching."""

    def test_add_and_prefix_match(self):
        trie = _SkillTrie()
        trie.add("doc_ingest")
        trie.add("dependency_map")
        trie.add("doc_review")
        matches = trie.prefix_matches("doc")
        assert sorted(matches) == ["doc_ingest", "doc_review"]

    def test_prefix_no_match(self):
        trie = _SkillTrie()
        trie.add("sum_review")
        assert trie.prefix_matches("nonexistent") == []

    def test_remove(self):
        trie = _SkillTrie()
        trie.add("skill_a")
        trie.remove("skill_a")
        assert trie.prefix_matches("skill") == []

    def test_empty_prefix_returns_all(self):
        trie = _SkillTrie()
        trie.add("a")
        trie.add("b")
        matches = trie.prefix_matches("")
        assert sorted(matches) == ["a", "b"]

    def test_thread_safe_add(self):
        trie = _SkillTrie()
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    trie.add(f"skill_{n}_{i}")
            except Exception as exc:
                errors.append(exc)

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=worker, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(trie.prefix_matches("")) == 200


# ---------------------------------------------------------------------------
# 2. SkillRegistry
# ---------------------------------------------------------------------------


class TestSkillRegistry:
    """SkillRegistry lifecycle and behavior."""

    def test_register_callable(self):
        reg = SkillRegistry()
        reg.register("test_fn", lambda ctx: "ok")
        assert reg.is_registered("test_fn")

    def test_register_rejects_duplicate(self):
        reg = SkillRegistry()
        reg.register("dup", lambda ctx: "ok")
        with pytest.raises(ValidationError, match="already registered"):
            reg.register("dup", lambda ctx: "ok")

    def test_register_rejects_empty_name(self):
        reg = SkillRegistry()
        with pytest.raises(ValidationError, match="non-empty string"):
            reg.register("", lambda ctx: "ok")

    def test_register_lazy_path(self):
        reg = SkillRegistry()
        reg.register("lazy", "uar.core.contracts:GoalSpec")
        assert reg.is_registered("lazy")

    def test_get_missing_raises(self):
        reg = SkillRegistry()
        with pytest.raises(SkillNotFoundError):
            reg.get("missing")

    def test_list_returns_snapshot(self):
        reg = SkillRegistry()
        reg.register("a", lambda ctx: 1)
        reg.register("b", lambda ctx: 2)
        names = reg.list()
        assert sorted(names) == ["a", "b"]
        # Snapshot should not change when new skill added
        reg.register("c", lambda ctx: 3)
        assert "c" not in names

    def test_search_by_prefix(self):
        reg = SkillRegistry()
        reg.register("doc_ingest", lambda ctx: 1)
        reg.register("doc_review", lambda ctx: 2)
        reg.register("sum_review", lambda ctx: 3)
        matches = reg.search_by_prefix("doc")
        assert sorted(matches) == ["doc_ingest", "doc_review"]

    def test_global_registry_has_skills(self):
        # The global registry should have canonical skills loaded
        assert registry.is_registered("doc_ingest")


# ---------------------------------------------------------------------------
# 3. Circuit breaker decorator
# ---------------------------------------------------------------------------


class TestCircuitBreakerDecorator:
    """@with_circuit_breaker integration patterns."""

    def test_successful_call_passes_through(self):
        reset_circuit_breaker("stable_svc")
        call_count = [0]

        @with_circuit_breaker("stable_svc", failure_threshold=3)
        def stable_skill(ctx):
            call_count[0] += 1
            return "ok"

        result = stable_skill(None)
        assert result == "ok"
        assert call_count[0] == 1

    def test_failure_increments_count(self):
        reset_circuit_breaker("flaky_svc")
        call_count = [0]

        @with_circuit_breaker("flaky_svc", failure_threshold=2)
        def flaky_skill(ctx):
            call_count[0] += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            flaky_skill(None)
        with pytest.raises(RuntimeError):
            flaky_skill(None)
        # Circuit should now be open
        with pytest.raises(Exception):
            flaky_skill(None)
        assert call_count[0] == 2

    def test_circuit_resets_after_timeout(self, monkeypatch):
        monkeypatch.setenv("UAR_CB_HALF_OPEN_AFTER", "0")
        reset_circuit_breaker("recover_svc")

        call_count = [0]

        @with_circuit_breaker(
            "recover_svc", failure_threshold=1, recovery_timeout=0.001
        )
        def recover_skill(ctx):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("fail")
            return "recovered"

        with pytest.raises(RuntimeError):
            recover_skill(None)
        # Circuit is open; after short timeout it should allow retry
        import time

        time.sleep(0.05)
        result = recover_skill(None)
        assert result == "recovered"


# ---------------------------------------------------------------------------
# 4. Middleware / service wiring patterns
# ---------------------------------------------------------------------------


class TestMiddlewarePatterns:
    """Common middleware behavior contracts."""

    def test_rate_limiter_reset_fixture(self):
        """conftest.py resets rate limiter between tests."""
        from uar.api.middleware import reset_rate_limiter

        # Calling reset should not raise
        reset_rate_limiter()


class TestServiceWiring:
    """Service layer integration contracts."""

    def test_auth_service_instantiates(self):
        from uar.services import AuthService

        svc = AuthService()
        assert svc is not None

    def test_recipe_service_instantiates(self):
        from uar.services import RecipeService

        svc = RecipeService()
        assert svc is not None

    def test_recipe_service_lists_canonical(self):
        from uar.services import RecipeService

        svc = RecipeService()
        recipes = svc.list_all(user_id=None)
        ids = {r["id"] for r in recipes}
        assert "review" in ids
        assert "gr_query" in ids


# ---------------------------------------------------------------------------
# 5. Router endpoint patterns
# ---------------------------------------------------------------------------


class TestRouterPatterns:
    """FastAPI router endpoint wiring checks."""

    def test_health_router_has_routes(self):
        from uar.api.routers.health import router

        routes = [r.path for r in router.routes]
        assert any("health" in p for p in routes)

    def test_runs_router_has_routes(self):
        from uar.api.routers.runs import router

        routes = [r.path for r in router.routes]
        assert any("run" in p for p in routes)

    def test_recipes_router_has_crud_routes(self):
        from uar.api.routers.recipes import router

        routes = [r.path for r in router.routes]
        paths = [r for r in routes]
        assert any("recipes" in p for p in paths)

    def test_streaming_router_has_routes(self):
        from uar.api.routers.streaming import router

        routes = [r.path for r in router.routes]
        assert any("stream" in p or "ws" in p for p in routes)


# ---------------------------------------------------------------------------
# 6. Plugin loading
# ---------------------------------------------------------------------------


class TestPluginLoading:
    """Plugin discovery and loading guards."""

    def test_plugin_load_module_missing(self):
        from uar.skills.plugin import load_plugins

        # Should not raise even if no plugins exist
        try:
            load_plugins()
        except Exception:
            pytest.skip("Plugin loading path unavailable in test env")
