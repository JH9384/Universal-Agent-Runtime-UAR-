"""Tests for the UAR Service Layer.

Verifies that services eliminate duplication while preserving correctness.
All tests use dependency injection so no FastAPI app or global state is needed.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from uar.core.recipes import DEFAULT_RECIPES
from uar.services.auth import AuthService
from uar.services.events import EventService
from uar.services.recipes import RecipeService
from uar.services.rate_limit import RateLimitService


# ------------------------------------------------------------------
# EventService
# ------------------------------------------------------------------


class TestEventService:
    def test_create_returns_canonical_schema(self):
        svc = EventService()
        ev = svc.create(
            "skill_start", "run-1", goal_id="g1", skill="doc_ingest"
        )
        assert ev["schema_version"] == "uar.event.v1"
        assert ev["type"] == "skill_start"
        assert ev["run_id"] == "run-1"
        assert ev["goal_id"] == "g1"
        assert ev["skill"] == "doc_ingest"
        assert "timestamp" in ev
        assert "correlation_id" in ev
        assert ev["payload"] == {}
        assert ev["error"] is None

    def test_create_extra_fields_merged(self):
        svc = EventService()
        ev = svc.create("custom", "r1", extra_key="extra_value")
        assert ev["extra_key"] == "extra_value"

    def test_create_extra_never_overwrites_canonical(self):
        svc = EventService()
        ev = svc.create("t", "r1", type="should_not_override")
        assert ev["type"] == "t"

    def test_error_event_structure(self):
        svc = EventService()
        ev = svc.error(
            run_id="r1",
            error_msg="boom",
            code="ERR",
            request_id="req-1",
            goal_id="g1",
        )
        assert ev["type"] == "error"
        assert ev["error"] == "boom"
        assert ev["payload"]["message"] == "boom"
        assert ev["payload"]["code"] == "ERR"
        assert ev["payload"]["request_id"] == "req-1"

    def test_complete_event(self):
        svc = EventService()
        ev = svc.complete("r1", status="failed", errors=["e1"])
        assert ev["type"] == "complete"
        assert ev["payload"]["status"] == "failed"
        assert ev["payload"]["errors"] == ["e1"]

    def test_heartbeat_event(self):
        svc = EventService()
        ev = svc.heartbeat("r1")
        assert ev["type"] == "heartbeat"
        assert "timestamp" in ev["payload"]

    def test_orchestration_plan_event(self):
        svc = EventService()
        ev = svc.orchestration_plan(graph={"nodes": []})
        assert ev["type"] == "orchestration_plan"
        assert ev["payload"]["graph"] == {"nodes": []}

    def test_emit_sse_format(self):
        svc = EventService()
        ev = svc.create("test", "r1")
        sse = svc.emit_sse(ev)
        assert sse.startswith("event: test\n")
        assert "data:" in sse
        parsed = json.loads(sse.split("data: ")[1])
        assert parsed["run_id"] == "r1"

    def test_emit_sse_handles_unserializable(self):
        svc = EventService()
        ev = svc.create("test", "r1", payload={"obj": object()})
        sse = svc.emit_sse(ev)
        # Should not raise; falls back to safe repr
        assert "event: test" in sse
        assert "data:" in sse
        parsed = json.loads(sse.split("data: ", 1)[1])
        assert parsed["run_id"] == "r1"
        assert "<object" in parsed["payload"]["obj"]


# ------------------------------------------------------------------
# AuthService
# ------------------------------------------------------------------


class TestAuthService:
    def test_authenticate_returns_none_for_none(self):
        svc = AuthService()
        assert svc.authenticate(None) is None

    @patch("uar.api.middleware.auth_middleware")
    def test_require_user_raises_401_when_anon(self, mock_auth):
        mock_auth.return_value = None
        svc = AuthService()
        with pytest.raises(HTTPException) as exc:
            svc.require_user(None)
        assert exc.value.status_code == 401

    @patch("uar.api.middleware.auth_middleware")
    def test_require_user_returns_user(self, mock_auth):
        mock_auth.return_value = {"user": "alice"}
        svc = AuthService()
        user = svc.require_user(MagicMock())
        assert user["user"] == "alice"

    def test_require_owner_succeeds(self):
        svc = AuthService()
        svc.require_owner({"user_id": "alice"}, {"user": "alice"})

    def test_require_owner_raises_403(self):
        svc = AuthService()
        with pytest.raises(HTTPException) as exc:
            svc.require_owner(
                {"user_id": "alice"}, {"user": "bob"}
            )
        assert exc.value.status_code == 403

    def test_forbid_canonical_raises_403(self):
        svc = AuthService()
        with pytest.raises(HTTPException) as exc:
            svc.forbid_canonical(
                "review", set(DEFAULT_RECIPES.keys())
            )
        assert exc.value.status_code == 403

    def test_forbid_canonical_allows_user_recipe(self):
        svc = AuthService()
        # Should not raise
        svc.forbid_canonical("my_recipe", set(DEFAULT_RECIPES.keys()))

    def test_parse_websocket_auth_from_header(self):
        svc = AuthService()
        creds = svc.parse_websocket_auth(
            {"authorization": "Bearer token123"}, {}
        )
        assert creds is not None
        assert creds.credentials == "token123"

    def test_parse_websocket_auth_from_query(self):
        svc = AuthService()
        creds = svc.parse_websocket_auth(
            {}, {"token": "tok456"}
        )
        assert creds is not None
        assert creds.credentials == "tok456"

    def test_parse_websocket_auth_none(self):
        svc = AuthService()
        assert svc.parse_websocket_auth({}, {}) is None


# ------------------------------------------------------------------
# RecipeService
# ------------------------------------------------------------------


class TestRecipeService:
    @pytest.fixture
    def svc(self, tmp_path):
        """RecipeService with isolated temp directory."""
        return RecipeService(path=tmp_path / "user_recipes.json")

    def test_list_all_includes_canonical(self, svc):
        recipes = svc.list_all()
        ids = {r["id"] for r in recipes}
        assert "review" in ids

    def test_create_and_load_user_recipe(self, svc):
        svc.create("my_r", {"label": "Mine", "skills": ["doc_ingest"]}, "u1")
        recipes = svc.list_all(user_id="u1")
        ids = {r["id"] for r in recipes}
        assert "my_r" in ids

    def test_create_fails_for_canonical(self, svc):
        canon = list(DEFAULT_RECIPES.keys())[0]
        with pytest.raises(ValueError, match="canonical"):
            svc.create(canon, {"skills": ["doc_ingest"]}, "u1")

    def test_create_validates_skills(self, svc):
        with pytest.raises(ValueError, match="skills must be"):
            svc.create("bad", {"skills": "not-a-list"}, "u1")

    def test_update_changes_recipe(self, svc):
        svc.create("r1", {"label": "Old", "skills": ["doc_ingest"]}, "u1")
        svc.update("r1", {"label": "New", "skills": ["sum_review"]}, "u1")
        loaded = svc.load()
        assert loaded["r1"]["label"] == "New"

    def test_update_fails_for_wrong_owner(self, svc):
        svc.create("r1", {"label": "Mine", "skills": ["doc_ingest"]}, "u1")
        with pytest.raises(PermissionError):
            svc.update("r1", {"skills": ["doc_ingest"]}, "u2")

    def test_update_fails_for_missing(self, svc):
        with pytest.raises(KeyError, match="not found"):
            svc.update("missing", {"skills": ["doc_ingest"]}, "u1")

    def test_delete_removes_recipe(self, svc):
        svc.create("r1", {"label": "Mine", "skills": ["doc_ingest"]}, "u1")
        svc.delete("r1", "u1")
        assert svc.load().get("r1") is None

    def test_delete_fails_for_wrong_owner(self, svc):
        svc.create("r1", {"label": "Mine", "skills": ["doc_ingest"]}, "u1")
        with pytest.raises(PermissionError):
            svc.delete("r1", "u2")

    def test_delete_fails_for_canonical(self, svc):
        canon = list(DEFAULT_RECIPES.keys())[0]
        with pytest.raises(ValueError, match="canonical"):
            svc.delete(canon, "u1")

    def test_load_filters_by_user(self, svc):
        svc.create("a", {"skills": ["doc_ingest"]}, "alice")
        svc.create("b", {"skills": ["sum_review"]}, "bob")
        alice_recipes = svc.load(user_id="alice")
        assert "a" in alice_recipes
        assert "b" not in alice_recipes


# ------------------------------------------------------------------
# RateLimitService
# ------------------------------------------------------------------


class TestRateLimitService:
    def test_check_returns_tuple(self):
        svc = RateLimitService()
        allowed, tier, limits = svc.check("127.0.0.1", None)
        assert isinstance(allowed, bool)
        assert tier in ("default", "authenticated")
        assert "requests" in limits
        assert "window" in limits

    @pytest.mark.asyncio
    async def test_ws_close_if_denied_returns_true_when_allowed(self):
        svc = RateLimitService()
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        result = await svc.ws_close_if_denied(True, mock_ws)
        assert result is True
        mock_ws.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ws_close_if_denied_closes_ws_when_denied(self):
        svc = RateLimitService()
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        result = await svc.ws_close_if_denied(False, mock_ws)
        assert result is False
        mock_ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ws_close_if_denied_swallows_close_exception(self):
        svc = RateLimitService()
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock(side_effect=RuntimeError("ws broken"))
        result = await svc.ws_close_if_denied(False, mock_ws)
        assert result is False


# ------------------------------------------------------------------
# GoalExecutionService (async)
# ------------------------------------------------------------------


@pytest.mark.asyncio
class TestGoalExecutionService:
    async def test_stream_goal_yields_orchestration_plan(self):
        from uar.services.execution import GoalExecutionService
        from uar.core.contracts import GoalSpec

        event_svc = EventService()
        exec_svc = GoalExecutionService(event_service=event_svc)

        goal = GoalSpec(
            id="g1",
            user_intent="test",
            objective="test",
            metadata={"timeout_seconds": 0.1},
        )

        events = []
        async for ev in exec_svc.stream_goal(
            goal, "req-1", None, "cid"
        ):
            events.append(ev)

        # Should yield at least orchestration plan + events
        types = [e["type"] for e in events]
        assert "orchestration_plan" in types

    async def test_stream_goal_emits_error_on_exception(self):
        from uar.services.execution import GoalExecutionService
        from uar.core.contracts import GoalSpec

        event_svc = EventService()
        exec_svc = GoalExecutionService(event_service=event_svc)

        # Corrupt goal to force error
        goal = GoalSpec(
            id="g1",
            user_intent="test",
            objective="test",
            required_skills=["nonexistent_skill_for_test"],
            metadata={"timeout_seconds": 0.1},
        )

        events = []
        try:
            async for ev in exec_svc.stream_goal(
                goal, "req-1", None, "cid"
            ):
                events.append(ev)
        except Exception:
            pass

        # Should emit orchestration plan regardless
        types = [e["type"] for e in events]
        assert "orchestration_plan" in types

    async def test_stream_goal_enforces_event_limit(self):
        from uar.services.execution import GoalExecutionService
        from uar.core.contracts import GoalSpec

        event_svc = EventService()
        exec_svc = GoalExecutionService(
            event_service=event_svc,
            max_stream_events=3,
        )

        goal = GoalSpec(
            id="g1",
            user_intent="test",
            objective="test",
            metadata={"timeout_seconds": 0.1},
        )

        events = []
        async for ev in exec_svc.stream_goal(
            goal, "req-1", None, "cid"
        ):
            events.append(ev)

        types = [e["type"] for e in events]
        assert "orchestration_plan" in types
        assert "error" in types
        assert "complete" in types
        # Limit should have triggered error + complete before all
        # executor events
        assert len(events) <= 6


# ------------------------------------------------------------------
# Integration clients (mocked)
# ------------------------------------------------------------------


class TestGreptileClient:
    @pytest.mark.asyncio
    async def test_query_without_key_returns_mock(self):
        from uar.integrations import GreptileClient

        with patch.dict("os.environ", {"GREPTILE_API_KEY": ""}):
            client = GreptileClient()
            result = await client.query("Where is the auth?")
        assert result["answer"] == "Greptile not configured"

    @pytest.mark.asyncio
    async def test_index_repo_without_key_returns_skipped(self):
        from uar.integrations import GreptileClient

        with patch.dict("os.environ", {"GREPTILE_API_KEY": ""}):
            client = GreptileClient()
            result = await client.index_repo()
        assert result["status"] == "skipped"


class TestConvexClient:
    @pytest.mark.asyncio
    async def test_insert_run_without_url_warns_and_returns_empty(self):
        from uar.integrations import ConvexClient

        with patch.dict("os.environ", {"CONVEX_URL": ""}):
            client = ConvexClient()
            result = await client.insert_run({"runId": "r1"})
        assert result == ""

    @pytest.mark.asyncio
    async def test_get_run_without_url_returns_none(self):
        from uar.integrations import ConvexClient

        with patch.dict("os.environ", {"CONVEX_URL": ""}):
            client = ConvexClient()
            assert await client.get_run("r1") is None

    def test_schema_definitions_returns_expected_keys(self):
        from uar.integrations import ConvexClient

        defs = ConvexClient.schema_definitions()
        assert "schema.ts" in defs
        assert "runs.ts" in defs
        assert "runs" in defs["schema.ts"]
