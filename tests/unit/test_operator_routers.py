"""Tests for operator dashboard routers.

Tests async endpoint functions directly since routers are not
mounted in the main FastAPI app.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestAnalyticsRouter:
    """Graph analytics endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_analytics(self):
        from uar.api.routers.operator.analytics import get_graph_analytics
        with patch("uar.api.routers.operator.analytics.store") as m:
            m.get_recommendation_metadata.return_value = []
            m.get_outcomes.return_value = []
            result = await get_graph_analytics("run-1", credentials=None)
            assert result["center_id"] == "run-1"
            assert "node_count" in result

    @pytest.mark.asyncio
    async def test_get_graph_analytics_center_type(self):
        from uar.api.routers.operator.analytics import get_graph_analytics
        with patch("uar.api.routers.operator.analytics.store"):
            result = await get_graph_analytics(
                "rec-1", center_type="recommendation", credentials=None
            )
            assert result["center_type"] == "recommendation"


class TestBriefingRouter:
    """Morning briefing endpoint."""

    @pytest.mark.asyncio
    async def test_get_briefing(self):
        from uar.api.routers.operator.briefing import get_briefing
        with patch("uar.api.routers.operator.briefing.store") as m:
            m.get_outcomes.return_value = []
            m.get_recommendation_metadata.return_value = []
            result = await get_briefing(credentials=None)
            assert "greeting" in result
            assert "generated_at" in result
            assert "summary_text" in result

    @pytest.mark.asyncio
    async def test_get_briefing_with_trust(self):
        from uar.api.routers.operator.briefing import get_briefing
        with patch("uar.api.routers.operator.briefing.store") as m:
            m.get_outcomes.return_value = []
            m.get_recommendation_metadata.return_value = []
            with patch("uar.core.trust_engine.compute_trust") as mt:
                mt.return_value = {
                    "recommendation_types": [
                        {"type": "test", "trust_score": 0.9,
                         "drift_penalty": 0.1}
                    ]
                }
                result = await get_briefing(credentials=None)
                assert result["drift_events"] >= 1


class TestGraphRouter:
    """Knowledge graph endpoint."""

    @pytest.mark.asyncio
    async def test_get_knowledge_graph(self):
        from uar.api.routers.operator.graph import get_knowledge_graph
        with patch("uar.api.routers.operator.graph.store") as m:
            m.get_by_run_id.return_value = None
            m.get_recommendation_metadata.return_value = []
            m.get_outcomes.return_value = []
            result = await get_knowledge_graph("run-1", credentials=None)
            assert "nodes" in result
            assert "edges" in result

    @pytest.mark.asyncio
    async def test_get_knowledge_graph_with_data(self):
        from uar.api.routers.operator.graph import get_knowledge_graph
        rec = MagicMock()
        rec.goal_id = "goal-1"
        rec.goal = {"id": "goal-1"}
        with patch("uar.api.routers.operator.graph.store") as m:
            m.get_by_run_id.return_value = rec
            m.get_recommendation_metadata.return_value = [
                {"run_id": "run-1", "recommendation_id": "rec-1",
                 "title": "Test"}
            ]
            m.get_outcomes.return_value = []
            result = await get_knowledge_graph("run-1", credentials=None)
            assert any(n["type"] == "goal" for n in result["nodes"])


class TestInsightsRouter:
    """Insight generation endpoints."""

    @pytest.mark.asyncio
    async def test_get_incident_patterns_empty(self):
        from uar.api.routers.operator.insights import get_incident_patterns
        with patch(
            "uar.api.routers.operator.insights._load_all_incidents"
        ) as m:
            m.return_value = []
            result = await get_incident_patterns(credentials=None)
            assert result["narrative"] == "No incidents to analyze."

    @pytest.mark.asyncio
    async def test_get_incident_patterns_with_data(self):
        from uar.api.routers.operator.insights import get_incident_patterns
        with patch(
            "uar.api.routers.operator.insights._load_all_incidents"
        ) as m:
            m.return_value = [
                {
                    "id": "inc-1",
                    "title": "test failure",
                    "severity": "high",
                    "status": "open",
                    "linked_run_ids": ["run-1"],
                    "created_at": 1000,
                    "updated_at": 2000,
                }
            ]
            result = await get_incident_patterns(credentials=None)
            assert "narrative" in result
            assert result["total_incidents"] == 1


class TestInvestigationsRouter:
    """Investigations endpoint."""

    @pytest.mark.asyncio
    async def test_investigate_run(self):
        from uar.api.routers.operator.investigations import investigate_run
        with patch("uar.api.routers.operator.investigations.store") as m:
            m.get_by_run_id.return_value = None
            result = await investigate_run("run-1", credentials=None)
            assert result["run_id"] == "run-1"
            assert result["status"] == "investigating"

    @pytest.mark.asyncio
    async def test_list_investigations(self):
        from uar.api.routers.operator.investigations import (
            list_investigations,
        )
        with patch(
            "uar.api.routers.operator.investigations._load_all_investigations"
        ) as m:
            m.return_value = []
            result = await list_investigations(credentials=None)
            assert result == []

    @pytest.mark.asyncio
    async def test_get_investigation_found(self):
        from uar.api.routers.operator.investigations import get_investigation
        with patch(
            "uar.api.routers.operator.investigations._load_all_investigations"
        ) as m:
            m.return_value = [{"id": "inv-1", "status": "active"}]
            result = await get_investigation("inv-1", credentials=None)
            assert result["id"] == "inv-1"

    @pytest.mark.asyncio
    async def test_get_investigation_not_found(self):
        from uar.api.routers.operator.investigations import get_investigation
        with patch(
            "uar.api.routers.operator.investigations._load_all_investigations"
        ) as m:
            m.return_value = []
            with pytest.raises(Exception):
                await get_investigation("inv-1", credentials=None)


class TestSearchRouter:
    """Search endpoint."""

    @pytest.mark.asyncio
    async def test_search_empty(self):
        from uar.api.routers.operator.search import search_all
        with patch("uar.api.routers.operator.search.store") as m:
            m.list_records.return_value = []
            result = await search_all(
                "test", types=None, limit=20, credentials=None
            )
            assert "results" in result

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        from uar.api.routers.operator.search import search_all
        with patch("uar.api.routers.operator.search.store") as m:
            m.list_records.return_value = [
                {"run_id": "test-run-1", "goal": {"text": "test query"}}
            ]
            result = await search_all(
                "test", types=None, limit=20, credentials=None
            )
            assert result["results"]


class TestTimeMachineRouter:
    """Time machine endpoint."""

    @pytest.mark.asyncio
    async def test_list_snapshots(self):
        from uar.api.routers.operator.time_machine import list_snapshots
        with patch(
            "uar.api.routers.operator.time_machine._load_all_snapshots"
        ) as m:
            m.return_value = []
            result = await list_snapshots(credentials=None)
            assert result == []

    @pytest.mark.asyncio
    async def test_create_snapshot(self):
        from uar.api.routers.operator.time_machine import create_snapshot
        with patch("uar.api.routers.operator.time_machine.store") as m:
            m.get_outcomes.return_value = []
            m.get_recommendation_metadata.return_value = []
            m.list_records.return_value = []
            with patch(
                "uar.api.routers.operator.time_machine._persist_snapshot"
            ):
                result = await create_snapshot(credentials=None)
                assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_snapshot_found(self):
        from uar.api.routers.operator.time_machine import get_snapshot
        with patch("uar.api.routers.operator.time_machine.store") as m:
            m.get_metadata.return_value = '{"timestamp": 123}'
            result = await get_snapshot(123, credentials=None)
            assert result["timestamp"] == 123

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found(self):
        from uar.api.routers.operator.time_machine import get_snapshot
        with patch("uar.api.routers.operator.time_machine.store") as m:
            m.get_metadata.return_value = None
            with pytest.raises(Exception):
                await get_snapshot(123, credentials=None)

    @pytest.mark.asyncio
    async def test_compare_snapshots(self):
        from uar.api.routers.operator.time_machine import compare_snapshots
        with patch("uar.api.routers.operator.time_machine.store") as m:
            m.get_metadata.return_value = None
            result = await compare_snapshots(1, 2, credentials=None)
            assert "snapshot_a" in result
            assert "snapshot_b" in result


class TestTrustExplorerRouter:
    """Trust explorer endpoint."""

    @pytest.mark.asyncio
    async def test_get_trust_explorer(self):
        from uar.api.routers.operator.trust_explorer import (
            get_trust_explorer,
        )
        with patch("uar.api.routers.operator.trust_explorer.store") as m:
            m.get_outcomes.return_value = []
            m.get_recommendation_metadata.return_value = []
            with patch("uar.core.trust_engine.compute_trust") as mt:
                mt.return_value = {
                    "recommendation_types": [
                        {"type": "test", "trust_score": 0.9}
                    ]
                }
                with patch(
                    "uar.core.effectiveness_ranking.compute_effectiveness"
                ) as me:
                    me.return_value = {"recommendation_types": []}
                    with patch(
                        "uar.core.evidence.aggregate_evidence"
                    ) as ma:
                        ma.return_value = {"recommendation_types": []}
                        with patch(
                            "uar.core.calibration.compute_calibration"
                        ) as mc:
                            mc.return_value = {"types": []}
                            result = await get_trust_explorer(
                                "test", credentials=None
                            )
                            assert "trust_score" in result
