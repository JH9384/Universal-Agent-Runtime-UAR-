"""Tests for advanced configuration validation.

Covers Neo4j, OpenAI, budget, Dagster, and combined validation.
"""

import os
from unittest.mock import patch

from uar.config_advanced import (
    validate_neo4j_config,
    validate_openai_config,
    validate_budget_config,
    validate_dagster_config,
    validate_advanced_config,
    log_validation_results,
    setup_default_budget_config,
)


class TestValidateNeo4j:
    """Neo4j configuration validation."""

    def test_all_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = validate_neo4j_config()
        assert result["valid"] is False
        assert any("NEO4J_CONNECTION_URI" in i for i in result["issues"])
        assert any("NEO4J_PASSWORD" in i for i in result["issues"])

    def test_bad_uri(self):
        env = {
            "NEO4J_CONNECTION_URI": "http://bad",
            "NEO4J_USERNAME": "user",
            "NEO4J_PASSWORD": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            result = validate_neo4j_config()
        assert result["valid"] is True
        assert any("bolt://" in w for w in result["warnings"])

    def test_valid(self):
        env = {
            "NEO4J_CONNECTION_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "pass",
        }
        with patch.dict("os.environ", env, clear=True):
            result = validate_neo4j_config()
        assert result["valid"] is True
        assert result["issues"] == []


class TestValidateOpenAI:
    """OpenAI configuration validation."""

    def test_missing_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = validate_openai_config()
        assert result["valid"] is False
        assert any("OPENAI_API_KEY" in i for i in result["issues"])

    def test_valid_key(self):
        env = {"OPENAI_API_KEY": "sk-test123"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_openai_config()
        assert result["valid"] is True

    def test_bad_base_url(self):
        env = {"OPENAI_API_KEY": "sk-test", "OPENAI_BASE_URL": "not-url"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_openai_config()
        assert result["valid"] is False
        assert any("BASE_URL" in i for i in result["issues"])

    def test_unusual_key_format(self):
        env = {"OPENAI_API_KEY": "not-sk-prefix"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_openai_config()
        assert result["valid"] is True
        assert any("format unusual" in w for w in result["warnings"])


class TestValidateBudget:
    """Budget configuration validation."""

    def test_all_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = validate_budget_config()
        assert result["valid"] is True
        assert len(result["warnings"]) > 0

    def test_bad_max_tokens(self):
        env = {"DEFAULT_MAX_TOKENS": "abc"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False
        assert any("integer" in i.lower() for i in result["issues"])

    def test_negative_max_tokens(self):
        env = {"DEFAULT_MAX_TOKENS": "-1"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False
        assert any("positive" in i.lower() for i in result["issues"])

    def test_very_large_tokens_warning(self):
        env = {"DEFAULT_MAX_TOKENS": "20000000"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is True
        assert any("very large" in w.lower() for w in result["warnings"])

    def test_bad_max_api_calls(self):
        env = {"DEFAULT_MAX_API_CALLS": "xyz"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False

    def test_bad_max_cost(self):
        env = {"DEFAULT_MAX_COST_USD": "free"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False

    def test_normal_max_tokens(self):
        """0 < tokens <= 10000000 branch."""
        env = {"DEFAULT_MAX_TOKENS": "5000"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is True
        assert result["warnings"] == []
        assert result["issues"] == []

    def test_negative_max_api_calls(self):
        env = {"DEFAULT_MAX_API_CALLS": "-1"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False
        assert any("positive" in i.lower() for i in result["issues"])

    def test_negative_max_cost(self):
        env = {"DEFAULT_MAX_COST_USD": "-1"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is False
        assert any("positive" in i.lower() for i in result["issues"])

    def test_positive_max_api_calls(self):
        """Positive max_api_calls, no issues or warnings."""
        env = {"DEFAULT_MAX_TOKENS": "100", "DEFAULT_MAX_API_CALLS": "5"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is True
        assert result["issues"] == []
        assert result["warnings"] == []

    def test_positive_max_cost(self):
        """Positive max_cost, no issues or warnings."""
        env = {"DEFAULT_MAX_TOKENS": "100", "DEFAULT_MAX_COST_USD": "5.0"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_budget_config()
        assert result["valid"] is True
        assert result["issues"] == []
        assert result["warnings"] == []


class TestValidateDagster:
    """Dagster configuration validation."""

    def test_all_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = validate_dagster_config()
        assert result["valid"] is True

    def test_user_without_password(self):
        env = {"DAGSTER_POSTGRES_USER": "user"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_dagster_config()
        assert result["valid"] is False

    def test_password_without_user(self):
        env = {"DAGSTER_POSTGRES_PASSWORD": "pass"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_dagster_config()
        assert result["valid"] is False

    def test_dagster_home_set(self):
        """DAGSTER_HOME set, no postgres vars → valid, no warning."""
        env = {"DAGSTER_HOME": "/opt/dagster"}
        with patch.dict("os.environ", env, clear=True):
            result = validate_dagster_config()
        assert result["valid"] is True
        assert result["warnings"] == []


class TestValidateAdvanced:
    """Combined advanced configuration validation."""

    def test_combined(self):
        with patch.dict("os.environ", {}, clear=True):
            result = validate_advanced_config()
        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "neo4j" in result["results"]
        assert "openai" in result["results"]


class TestLogValidation:
    """Logging of validation results."""

    def test_valid(self):
        log_validation_results({"valid": True, "issues": [], "warnings": []})

    def test_with_issues(self):
        log_validation_results({
            "valid": False,
            "issues": ["error"],
            "warnings": ["warn"],
        })


class TestSetupDefaultBudget:
    """Default budget configuration setup."""

    def test_sets_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            setup_default_budget_config()
            assert os.environ["DEFAULT_MAX_TOKENS"] == "100000"
            assert os.environ["DEFAULT_MAX_API_CALLS"] == "1000"
            assert os.environ["DEFAULT_MAX_COST_USD"] == "10.0"

    def test_preserves_existing(self):
        env = {"DEFAULT_MAX_TOKENS": "50000"}
        with patch.dict("os.environ", env, clear=True):
            setup_default_budget_config()
            assert os.environ["DEFAULT_MAX_TOKENS"] == "50000"

    def test_all_existing(self):
        """All three vars already set → no changes."""
        env = {
            "DEFAULT_MAX_TOKENS": "1",
            "DEFAULT_MAX_API_CALLS": "2",
            "DEFAULT_MAX_COST_USD": "3",
        }
        with patch.dict("os.environ", env, clear=True):
            setup_default_budget_config()
            assert os.environ["DEFAULT_MAX_TOKENS"] == "1"
            assert os.environ["DEFAULT_MAX_API_CALLS"] == "2"
            assert os.environ["DEFAULT_MAX_COST_USD"] == "3"
