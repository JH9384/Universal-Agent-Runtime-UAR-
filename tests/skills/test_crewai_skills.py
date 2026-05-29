"""Tests for crewai_task and crewai_workflow skill wrappers."""

from unittest.mock import patch

from uar.skills.advanced_integrations import crewai_task, crewai_workflow


def _ctx(meta: dict) -> dict:
    return {"metadata": meta, "goal": "test goal"}


class TestCrewaiTaskFallback:
    """crewai_task with no crewai installed (UAR-native fallback)."""

    def test_researcher_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_task(
                _ctx({
                    "role": "researcher",
                    "task_description": "Research AI safety",
                })
            )
        assert result["status"] == "completed"
        assert result["mode"] == "uar_native"
        assert result["role"] == "researcher"
        assert "result" in result

    def test_analyst_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_task(
                _ctx({
                    "role": "analyst",
                    "task_description": "Analyze trends",
                })
            )
        assert result["status"] == "completed"
        assert result["mode"] == "uar_native"

    def test_unknown_role_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_task(
                _ctx({"role": "unknown_role"})
            )
        assert result["status"] == "completed"
        assert result["role"] == "unknown_role"

    def test_missing_dependency_no_crash(self):
        """Skill should not crash when crewai is missing."""
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_task(_ctx({"role": "coder"}))
        assert "status" in result
        assert result["mode"] == "uar_native"


class TestCrewaiTaskReal:
    """crewai_task when crewai IS available and LLM configured."""

    def test_real_crewai_path(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            True,
        ):
            with patch(
                "uar.core.crewai_real._crewai_available",
                return_value=True,
            ):
                with patch(
                    "uar.core.crewai_real._llm_configured",
                    return_value=True,
                ):
                    with patch(
                        "uar.core.crewai_real.execute_single_task",
                        return_value={
                            "status": "completed",
                            "mode": "crewai_real",
                            "raw_output": "Real output",
                        },
                    ):
                        result = crewai_task(
                            _ctx({"role": "writer"})
                        )
        assert result["status"] == "completed"
        assert result["mode"] == "crewai_real"
        assert result["skill"] == "crewai_task"

    def test_real_crewai_fallback_on_error(self):
        """If CrewAIRealError is raised, should fall back to UAR-native."""
        from uar.core.crewai_real import CrewAIRealError

        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            True,
        ):
            with patch(
                "uar.core.crewai_real.execute_single_task",
                side_effect=CrewAIRealError("no LLM"),
            ):
                result = crewai_task(_ctx({"role": "coder"}))
        assert result["status"] == "completed"
        assert result["mode"] == "uar_native"


class TestCrewaiWorkflowFallback:
    """crewai_workflow with no crewai installed."""

    def test_research_analyze_write_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_workflow(
                _ctx({"workflow_type": "research_analyze_write"})
            )
        assert "status" in result
        assert result["mode"] == "uar_native"
        assert result["workflow_type"] == "research_analyze_write"

    def test_code_review_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_workflow(
                _ctx({"workflow_type": "code_review"})
            )
        assert "status" in result
        assert result["mode"] == "uar_native"

    def test_data_analysis_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_workflow(
                _ctx({"workflow_type": "data_analysis"})
            )
        assert "status" in result
        assert result["mode"] == "uar_native"

    def test_unknown_workflow_fallback(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            False,
        ):
            result = crewai_workflow(
                _ctx({"workflow_type": "unknown"})
            )
        assert result["status"] == "error"
        assert "Unknown workflow" in result["error"]


class TestCrewaiWorkflowReal:
    """crewai_workflow when crewai IS available."""

    def test_real_crewai_path(self):
        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            True,
        ):
            with patch(
                "uar.core.crewai_real._crewai_available",
                return_value=True,
            ):
                with patch(
                    "uar.core.crewai_real._llm_configured",
                    return_value=True,
                ):
                    with patch(
                        "uar.core.crewai_real.execute_crew_workflow",
                        return_value={
                            "status": "completed",
                            "mode": "crewai_real",
                            "raw_output": "Workflow done",
                        },
                    ):
                        result = crewai_workflow(
                            _ctx({
                                "workflow_type": "research_analyze_write",
                            })
                        )
        assert result["status"] == "completed"
        assert result["mode"] == "crewai_real"
        assert result["skill"] == "crewai_workflow"

    def test_real_crewai_fallback_on_error(self):
        from uar.core.crewai_real import CrewAIRealError

        with patch(
            "uar.core.crewai_integration.CREWAI_AVAILABLE",
            True,
        ):
            with patch(
                "uar.core.crewai_real.execute_crew_workflow",
                side_effect=CrewAIRealError("no LLM"),
            ):
                result = crewai_workflow(
                    _ctx({"workflow_type": "research_analyze_write"})
                )
        assert "status" in result
        assert result["mode"] == "uar_native"
