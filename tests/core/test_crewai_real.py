"""Tests for crewai_real module.

Since ``crewai`` is not installed in the test environment these tests
verify the fallback / error paths directly and exercise the real code
path with mocked ``crewai``.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from uar.core.crewai_integration import AgentRole
from uar.core.crewai_real import (
    _crewai_available,
    _llm_configured,
    _map_role_to_crewai,
    CrewAIRealError,
    execute_single_task,
    execute_crew_workflow,
)


class TestAvailability:
    """Availability helpers."""

    def test_crewai_available_false(self):
        assert _crewai_available() is False

    def test_llm_configured_no_keys(self):
        # Ensure none of the keys are set
        for key in [
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
        ]:
            os.environ.pop(key, None)
        assert _llm_configured() is False

    def test_llm_configured_with_key(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            assert _llm_configured() is True
        finally:
            del os.environ["OPENAI_API_KEY"]


class TestMapRoleToCrewai:
    """Role mapping."""

    def test_all_roles_have_mapping(self):
        for role in AgentRole:
            cfg = _map_role_to_crewai(role)
            assert "role" in cfg
            assert "goal" in cfg
            assert "backstory" in cfg

    def test_researcher_mapping(self):
        cfg = _map_role_to_crewai(AgentRole.RESEARCHER)
        assert "Researcher" in cfg["role"]

    def test_specialist_fallback(self):
        cfg = _map_role_to_crewai(AgentRole.SPECIALIST)
        assert "Specialist" in cfg["role"]


class TestExecuteSingleTask:
    """execute_single_task error and mock paths."""

    def test_raises_when_crewai_missing(self):
        with pytest.raises(CrewAIRealError, match="not installed"):
            execute_single_task(
                role=AgentRole.RESEARCHER,
                task_description="Do research",
            )

    def test_raises_when_no_llm(self):
        with patch(
            "uar.core.crewai_real._crewai_available",
            return_value=True,
        ):
            with pytest.raises(CrewAIRealError, match="no LLM"):
                execute_single_task(
                    role=AgentRole.RESEARCHER,
                    task_description="Do research",
                )

    def test_real_path_with_mocked_crewai(self):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Mocked crew output"

        mock_agent_cls = MagicMock(return_value=MagicMock())
        mock_task_cls = MagicMock(return_value=MagicMock())
        mock_crew_cls = MagicMock(return_value=mock_crew)
        mock_process = MagicMock()
        mock_process.sequential = "sequential"

        crewai_mod = MagicMock()
        crewai_mod.Agent = mock_agent_cls
        crewai_mod.Task = mock_task_cls
        crewai_mod.Crew = mock_crew_cls
        crewai_mod.Process = mock_process

        with patch.dict("sys.modules", {"crewai": crewai_mod}):
            with patch(
                "uar.core.crewai_real._crewai_available",
                return_value=True,
            ):
                with patch(
                    "uar.core.crewai_real._llm_configured",
                    return_value=True,
                ):
                    result = execute_single_task(
                        role=AgentRole.ANALYST,
                        task_description="Analyze data",
                        expected_output="A report",
                    )

        assert result["status"] == "completed"
        assert result["mode"] == "crewai_real"
        assert result["agent_role"] == "analyst"
        assert result["raw_output"] == "Mocked crew output"
        mock_crew_cls.assert_called_once()
        mock_crew.kickoff.assert_called_once()


class TestExecuteCrewWorkflow:
    """execute_crew_workflow error and mock paths."""

    def test_raises_when_crewai_missing(self):
        with pytest.raises(CrewAIRealError, match="not installed"):
            execute_crew_workflow(
                task_specs=[{
                    "role": AgentRole.RESEARCHER, "description": "x",
                }],
            )

    def test_real_path_with_mocked_crewai(self):
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Workflow output"

        mock_agent_cls = MagicMock(return_value=MagicMock())
        mock_task_cls = MagicMock(return_value=MagicMock())
        mock_crew_cls = MagicMock(return_value=mock_crew)
        mock_process = MagicMock()
        mock_process.sequential = "sequential"
        mock_process.hierarchical = "hierarchical"

        crewai_mod = MagicMock()
        crewai_mod.Agent = mock_agent_cls
        crewai_mod.Task = mock_task_cls
        crewai_mod.Crew = mock_crew_cls
        crewai_mod.Process = mock_process

        with patch.dict("sys.modules", {"crewai": crewai_mod}):
            with patch(
                "uar.core.crewai_real._crewai_available",
                return_value=True,
            ):
                with patch(
                    "uar.core.crewai_real._llm_configured",
                    return_value=True,
                ):
                    result = execute_crew_workflow(
                        task_specs=[
                            {
                                "role": AgentRole.WRITER,
                                "description": "Write",
                                "expected_output": "Doc",
                            },
                        ],
                        process="sequential",
                    )

        assert result["status"] == "completed"
        assert result["mode"] == "crewai_real"
        assert result["task_count"] == 1
        mock_crew_cls.assert_called_once()
        mock_crew.kickoff.assert_called_once()
