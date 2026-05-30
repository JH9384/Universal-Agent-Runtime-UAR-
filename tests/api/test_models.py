"""Tests for uar.api.models."""

import pytest
from pydantic import ValidationError

from uar.api.models import RunRequest
from uar.core.registry import registry


class TestRunRequest:
    def test_valid_minimal(self):
        req = RunRequest(goal="test")
        assert req.goal == "test"

    def test_timeout_seconds_validation(self):
        req = RunRequest(goal="test", timeout_seconds=30.0)
        assert req.timeout_seconds == 30.0

    def test_validate_timeout_field_direct(self):
        assert RunRequest.validate_timeout_field(30.0) == 30.0

    def test_validate_timeout_field_none(self):
        assert RunRequest.validate_timeout_field(None) is None

    def test_execution_order_none(self):
        req = RunRequest(goal="test", execution_order=None)
        assert req.execution_order is None

    def test_execution_order_not_list(self):
        with pytest.raises(ValidationError):
            RunRequest(goal="test", execution_order="not_a_list")

    def test_validate_execution_order_not_list(self):
        with pytest.raises(ValueError, match="array"):
            RunRequest.validate_execution_order_field("not_a_list")

    def test_execution_order_item_not_dict(self):
        with pytest.raises(ValidationError):
            RunRequest(goal="test", execution_order=["string"])

    def test_validate_execution_order_item_not_dict(self):
        with pytest.raises(ValueError, match="object"):
            RunRequest.validate_execution_order_field(["string"])

    def test_execution_order_missing_type(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[{"content": "x", "id": "1"}],
            )

    def test_execution_order_missing_id(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[{"type": "skill", "content": "x"}],
            )

    def test_execution_order_invalid_type(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[{
                    "type": "invalid", "content": "x", "id": "1",
                }],
            )

    def test_execution_order_duplicate_id(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[
                    {"type": "skill", "content": "x", "id": "1"},
                    {"type": "skill", "content": "y", "id": "1"},
                ],
            )

    def test_execution_order_recipe_empty_content(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[{
                    "type": "recipe", "content": "", "id": "1",
                }],
            )

    def test_execution_order_known_skill(self):
        from unittest.mock import patch
        with patch.object(registry, "is_registered", return_value=True):
            req = RunRequest(
                goal="test",
                execution_order=[{
                    "type": "skill",
                    "content": "dummy_skill",
                    "id": "1",
                }],
            )
        assert len(req.execution_order) == 1

    def test_execution_order_mixed_types(self):
        from unittest.mock import patch
        with patch.object(registry, "is_registered", return_value=True):
            req = RunRequest(
                goal="test",
                execution_order=[
                    {"type": "recipe", "content": "my_recipe", "id": "1"},
                    {"type": "skill", "content": "dummy_skill", "id": "2"},
                ],
            )
        assert len(req.execution_order) == 2

    def test_execution_order_two_skills(self):
        from unittest.mock import patch
        with patch.object(registry, "is_registered", return_value=True):
            req = RunRequest(
                goal="test",
                execution_order=[
                    {"type": "skill", "content": "skill_a", "id": "1"},
                    {"type": "skill", "content": "skill_b", "id": "2"},
                ],
            )
        assert len(req.execution_order) == 2

    def test_execution_order_unknown_skill(self):
        with pytest.raises(ValidationError):
            RunRequest(
                goal="test",
                execution_order=[{
                    "type": "skill",
                    "content": "nonexistent_skill_xyz",
                    "id": "1",
                }],
            )
