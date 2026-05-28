"""Tests for advanced API endpoints.

Covers router definition and endpoint invocation with mocked deps.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from uar.api.advanced_endpoints import router


app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestRouter:
    """Router configuration."""

    def test_prefix(self):
        assert router.prefix == "/api/advanced"

    def test_tags(self):
        assert "advanced" in router.tags


class TestOrchestratorStatus:
    """/orchestrator/status endpoint."""

    def test_returns_status(self):
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {"agents": 2}
        with patch(
            "uar.core.agent_framework.get_orchestrator",
            return_value=mock_orch,
        ):
            resp = client.get("/api/advanced/orchestrator/status")
        assert resp.status_code == 200
        assert resp.json()["agents"] == 2


class TestGovernance:
    """Governance endpoints."""

    def _mock_gov(self):
        budget = MagicMock()
        budget.to_dict.return_value = {"agent_id": "a1", "max_tokens": 100}
        gov = MagicMock()
        gov.get_system_status.return_value = {"status": "ok"}
        gov.create_budget.return_value = budget
        gov.get_budget.return_value = budget
        v = MagicMock()
        v.to_dict.return_value = {"severity": "warning"}
        gov.guardrails.get_violations.return_value = [v]
        return gov

    def test_status(self):
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=self._mock_gov(),
        ):
            resp = client.get("/api/advanced/governance/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_create_budget(self):
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=self._mock_gov(),
        ):
            resp = client.post(
                "/api/advanced/governance/budget?agent_id=a1"
            )
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "a1"

    def test_get_budget(self):
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=self._mock_gov(),
        ):
            resp = client.get("/api/advanced/governance/budget/a1")
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "a1"

    def test_get_budget_not_found(self):
        gov = self._mock_gov()
        gov.get_budget.return_value = None
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=gov,
        ):
            resp = client.get("/api/advanced/governance/budget/unknown")
        assert resp.status_code == 404

    def test_violations(self):
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=self._mock_gov(),
        ):
            resp = client.get("/api/advanced/governance/violations")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_violations_with_severity(self):
        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=self._mock_gov(),
        ):
            resp = client.get(
                "/api/advanced/governance/violations?severity=warning"
            )
        assert resp.status_code == 200


class TestDagster:
    """Dagster endpoints."""

    def _mock_orchestrator(self):
        orch = MagicMock()
        orch.get_orchestrator_status.return_value = {"pipelines": 1}
        exec_result = MagicMock()
        exec_result.to_dict.return_value = {"status": "completed"}
        orch.execute_pipeline.return_value = exec_result
        return orch

    def test_status(self):
        with patch(
            "uar.core.dagster_orchestration.get_orchestrator",
            return_value=self._mock_orchestrator(),
        ):
            resp = client.get("/api/advanced/dagster/status")
        assert resp.status_code == 200
        assert resp.json()["pipelines"] == 1

    def test_execute_pipeline(self):
        with patch(
            "uar.core.dagster_orchestration.get_orchestrator",
            return_value=self._mock_orchestrator(),
        ):
            resp = client.post(
                "/api/advanced/dagster/pipeline?pipeline_name=test"
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


class TestGraphRAG:
    """GraphRAG endpoints."""

    def _mock_graphrag(self):
        gr = MagicMock()
        gr.get_graph_stats.return_value = {"nodes": 10}
        gr.query_graph.return_value = {"results": ["a"]}
        return gr

    def test_status(self):
        with patch(
            "uar.core.flexible_graphrag.get_graphrag_instance",
            return_value=self._mock_graphrag(),
        ):
            resp = client.get("/api/advanced/graphrag/status")
        assert resp.status_code == 200
        assert resp.json()["nodes"] == 10

    def test_query(self):
        mock_strategy = MagicMock()
        mock_strategy.VECTOR = "vector"
        mock_strategy.FULLTEXT = "fulltext"
        mock_strategy.PROPERTY_GRAPH = "property_graph"
        mock_strategy.RDF_SPARQL = "rdf_sparql"
        mock_strategy.HYBRID = "hybrid"
        with patch(
            "uar.core.flexible_graphrag.get_graphrag_instance",
            return_value=self._mock_graphrag(),
        ):
            with patch(
                "uar.core.flexible_graphrag.SearchStrategy",
                mock_strategy,
            ):
                resp = client.post(
                    "/api/advanced/graphrag/query?query=hello"
                )
        assert resp.status_code == 200


class TestCrewAI:
    """CrewAI endpoints."""

    def _mock_orchestrator(self):
        orch = MagicMock()
        orch.get_orchestrator_status.return_value = {
            "agents": {}, "tasks": {},
        }
        return orch

    def test_status(self):
        with patch(
            "uar.core.crewai_integration.get_task_orchestrator",
            return_value=self._mock_orchestrator(),
        ):
            resp = client.get("/api/advanced/crewai/status")
        assert resp.status_code == 200

    def test_create_agent(self):
        with patch(
            "uar.core.crewai_integration.get_task_orchestrator",
            return_value=self._mock_orchestrator(),
        ):
            resp = client.post(
                "/api/advanced/crewai/agent"
                "?role=researcher&agent_id=a1&name=Test"
            )
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "a1"
        assert resp.json()["role"] == "researcher"
        assert resp.json()["name"] == "Test"

    def test_execute_workflow(self):
        def _mock_workflow(*args, **kwargs):
            return {"status": "completed"}

        with patch(
            "uar.core.crewai_integration.execute_standard_workflow",
            new=_mock_workflow,
        ):
            resp = client.post(
                "/api/advanced/crewai/workflow"
                "?workflow_type=research_analyze_write",
                json={"topic": "AI"},
            )
        assert resp.status_code == 200
