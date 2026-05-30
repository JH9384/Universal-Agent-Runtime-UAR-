"""Tests for uar.skills.advanced_integrations."""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.advanced_integrations import (
    blackboard_message,
    guardrail_check,
    budget_status,
    blackboard_status,
    agent_workflow,
    crewai_task,
    llamaindex_rag,
    flexible_graphrag,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestBlackboard:
    def test_post(self):
        ctx = _ctx({"action": "post", "key": "k1", "value": "v1"})
        result = blackboard_message(ctx)
        assert result["status"] == "completed"
        assert result["action"] == "post"

    def test_post_missing_key(self):
        ctx = _ctx({"action": "post"})
        result = blackboard_message(ctx)
        assert result["status"] == "failed"

    def test_read(self):
        ctx = _ctx({"action": "post", "key": "k1", "value": "v1"})
        blackboard_message(ctx)
        ctx2 = _ctx({"action": "read", "key": "k1"})
        ctx2.data = ctx.data
        result = blackboard_message(ctx2)
        assert result["status"] == "completed"
        assert result["found"] is True
        assert result["value"] == "v1"

    def test_read_missing_key(self):
        ctx = _ctx({"action": "read", "key": "missing"})
        result = blackboard_message(ctx)
        assert result["status"] == "completed"
        assert result["found"] is False

    def test_read_not_found(self):
        ctx = _ctx({"action": "read", "key": "k1", "channel": "ch1"})
        result = blackboard_message(ctx)
        assert result["status"] == "completed"
        assert result["found"] is False

    def test_list(self):
        ctx = _ctx({"action": "post", "key": "k1", "value": "v1"})
        blackboard_message(ctx)
        ctx2 = _ctx({"action": "list"})
        ctx2.data = ctx.data
        result = blackboard_message(ctx2)
        assert result["status"] == "completed"
        assert "k1" in result["keys"]

    def test_unknown_action(self):
        ctx = _ctx({"action": "unknown"})
        result = blackboard_message(ctx)
        assert result["status"] == "failed"

    def test_non_dict_channel(self):
        ctx = _ctx({"action": "read", "key": "k1", "channel": "ch1"})
        ctx.data = {"blackboard": {"ch1": "not_dict"}}
        result = blackboard_message(ctx)
        assert result["status"] == "completed"
        assert result["found"] is False

    def test_non_dict_bb(self):
        ctx = _ctx({"action": "read", "key": "k1"})
        ctx.data = {"blackboard": "not_dict"}
        result = blackboard_message(ctx)
        assert result["status"] == "completed"

    def test_dict_ctx(self):
        ctx = {"metadata": {"action": "post", "key": "k1", "value": "v1"}}
        result = blackboard_message(ctx)
        assert result["status"] == "completed"


class TestGuardrailsCheck:
    def test_basic(self):
        v = MagicMock()
        v.to_dict.return_value = {"type": "test"}
        gov = MagicMock()
        gov.guardrails.check.return_value = [v]

        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=gov,
        ):
            with patch(
                "uar.core.guardrails.setup_default_guardrails"
            ):
                with patch(
                    "uar.core.guardrails.GuardrailType"
                ) as MockGT:
                    MockGT.CONTENT_SAFETY = "cs"
                    MockGT.RATE_LIMIT = "rl"
                    MockGT.BUDGET = "b"
                    MockGT.PERMISSION = "p"
                    MockGT.COMPLIANCE = "c"
                    MockGT.OUTPUT_VALIDATION = "ov"
                    result = guardrail_check(
                        _ctx({"guardrail_type": "rate_limit"})
                    )
        assert result["status"] == "success"
        assert result["guardrail_type"] == "rate_limit"
        assert result["violation_count"] == 1
        assert result["passed"] is False


class TestBudgetCheck:
    def test_existing(self):
        budget = MagicMock()
        budget.to_dict.return_value = {"limit": 100}
        gov = MagicMock()
        gov.get_budget.return_value = budget

        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=gov,
        ):
            result = budget_status(_ctx({"agent_id": "agent1"}))
        assert result["status"] == "success"
        assert result["budget"]["limit"] == 100

    def test_new_budget(self):
        budget = MagicMock()
        budget.to_dict.return_value = {"limit": 0}
        gov = MagicMock()
        gov.get_budget.return_value = None
        gov.budgets = {}

        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=gov,
        ):
            with patch(
                "uar.core.guardrails.Budget",
                return_value=budget,
            ):
                result = budget_status(_ctx({"agent_id": "agent1"}))
        assert result["status"] == "success"


class TestBlackboardStatus:
    def test_basic(self):
        gov = MagicMock()
        gov.blackboard.get_status.return_value = {"active": True}

        with patch(
            "uar.core.guardrails.get_governance_system",
            return_value=gov,
        ):
            result = blackboard_status(_ctx({}))
        assert result["status"] == "success"
        assert result["blackboard_status"]["active"] is True


class TestAgentWorkflow:
    def test_basic(self):
        with patch(
            "uar.core.agent_framework.get_orchestrator",
            return_value=MagicMock(),
        ):
            with patch(
                "uar.core.agent_framework.execute_agent_workflow",
                return_value={"workflow_id": "w1"},
            ):
                with patch(
                    "uar.skills.advanced_integrations.run_sync_safe",
                    return_value={
                        "status": "success",
                        "workflow_id": "w1",
                    },
                ):
                    with patch(
                        "uar.core.agent_framework.Agent"
                    ):
                        result = agent_workflow(
                            _ctx({
                                "agent_sequence": ["a1"],
                                "workflow_type": "seq",
                                "agents": [
                                    {"id": "a1", "name": "Agent1"},
                                ],
                            })
                        )
        assert result["status"] == "success"
        assert result["workflow_id"] == "w1"


class TestCrewaiTask:
    def test_basic(self):
        result = crewai_task(_ctx({
            "workflow_type": "research",
            "input_data": "test",
        }))
        assert "status" in result


class TestLlamaIndexRag:
    def test_missing_package(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = llamaindex_rag(_ctx({}))
        assert result["status"] == "completed"
        assert result["metadata"]["mode"] == "uar_native"


class TestFlexibleGraphrag:
    def test_missing_package(self):
        with patch(
            "uar.skills.advanced_integrations.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = flexible_graphrag(_ctx({}))
        assert result["status"] == "failed"
