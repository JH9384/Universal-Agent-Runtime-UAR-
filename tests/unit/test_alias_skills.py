"""Tests for uar.skills.alias_skills."""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.alias_skills import (
    auto_down,
    auto_status,
    auto_up,
    deps,
    review,
    eco_canon,
    eco_foundation,
    eco_status,
    gr_index,
    gr_query,
    gr_full,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestAutonomiAliases:
    def test_auto_down(self):
        with patch(
            "uar.skills.alias_skills.autonomi_download",
            return_value={"status": "completed"},
        ):
            result = auto_down(_ctx({}))
        assert result["status"] == "completed"

    def test_auto_status(self):
        with patch(
            "uar.skills.alias_skills.autonomi_status",
            return_value={"status": "completed"},
        ):
            result = auto_status(_ctx({}))
        assert result["status"] == "completed"

    def test_auto_up(self):
        with patch(
            "uar.skills.alias_skills.autonomi_upload",
            return_value={"status": "completed"},
        ):
            result = auto_up(_ctx({}))
        assert result["status"] == "completed"


class TestUtilityAliases:
    def test_deps(self):
        with patch(
            "uar.skills.alias_skills.dependency_map",
            return_value={"status": "completed"},
        ):
            result = deps(_ctx({}))
        assert result["status"] == "completed"

    def test_review(self):
        with patch(
            "uar.skills.alias_skills.sum_review",
            return_value={"status": "completed"},
        ):
            result = review(_ctx({}))
        assert result["status"] == "completed"


class TestEcoAliases:
    def test_eco_canon(self):
        with patch(
            "uar.skills.alias_skills.uor_addr_canonicalize",
            return_value={"status": "completed"},
        ):
            result = eco_canon(_ctx({}))
        assert result["status"] == "completed"

    def test_eco_foundation(self):
        with patch(
            "uar.skills.alias_skills.uor_foundation_verify",
            return_value={"status": "completed"},
        ):
            result = eco_foundation(_ctx({}))
        assert result["status"] == "completed"

    def test_eco_status(self):
        with patch(
            "uar.skills.alias_skills.uor_ecosystem_status",
            return_value={"status": "completed"},
        ):
            result = eco_status(_ctx({}))
        assert result["status"] == "completed"


class TestGraphragAliases:
    def test_gr_index(self):
        with patch(
            "uar.skills.alias_skills.graphrag_index",
            return_value={"status": "completed"},
        ):
            result = gr_index(_ctx({}))
        assert result["status"] == "completed"

    def test_gr_query(self):
        with patch(
            "uar.skills.alias_skills.graphrag_query",
            return_value={"status": "completed"},
        ):
            result = gr_query(_ctx({}))
        assert result["status"] == "completed"

    def test_gr_full_all_success(self):
        with patch(
            "uar.skills.alias_skills.graphrag_init",
            return_value={"status": "completed"},
        ):
            with patch(
                "uar.skills.alias_skills.graphrag_index",
                return_value={"status": "completed"},
            ):
                with patch(
                    "uar.skills.alias_skills.graphrag_query",
                    return_value={"status": "completed"},
                ):
                    result = gr_full(_ctx({}))
        assert result["status"] == "completed"
        assert "stages" in result

    def test_gr_full_init_fails(self):
        with patch(
            "uar.skills.alias_skills.graphrag_init",
            return_value={"status": "failed", "error": "init fail"},
        ):
            result = gr_full(_ctx({}))
        assert result["status"] == "failed"
        assert result["stage"] == "init"

    def test_gr_full_index_fails(self):
        with patch(
            "uar.skills.alias_skills.graphrag_init",
            return_value={"status": "completed"},
        ):
            with patch(
                "uar.skills.alias_skills.graphrag_index",
                return_value={"status": "failed", "error": "index fail"},
            ):
                result = gr_full(_ctx({}))
        assert result["status"] == "failed"
        assert result["stage"] == "index"

    def test_gr_full_query_fails(self):
        with patch(
            "uar.skills.alias_skills.graphrag_init",
            return_value={"status": "completed"},
        ):
            with patch(
                "uar.skills.alias_skills.graphrag_index",
                return_value={"status": "completed"},
            ):
                with patch(
                    "uar.skills.alias_skills.graphrag_query",
                    return_value={"status": "failed", "error": "query fail"},
                ):
                    result = gr_full(_ctx({}))
        assert result["status"] == "failed"
        assert result["stage"] == "query"
