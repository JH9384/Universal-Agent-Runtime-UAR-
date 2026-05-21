"""
Configuration validation for advanced framework integrations.

This module provides validation functions for the configuration
required by the advanced AI framework integrations.
"""

import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def validate_neo4j_config() -> Dict[str, Any]:
    """Validate Neo4j configuration for GraphRAG."""
    issues: List[str] = []
    warnings: List[str] = []

    connection_uri = os.getenv("NEO4J_CONNECTION_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not connection_uri:
        issues.append("NEO4J_CONNECTION_URI not set")
    elif not connection_uri.startswith(("bolt://", "neo4j://")):
        warnings.append(
            "NEO4J_CONNECTION_URI should start with bolt:// or neo4j://"
        )

    if not username:
        warnings.append("NEO4J_USERNAME not set (default: neo4j)")

    if not password:
        issues.append("NEO4J_PASSWORD not set")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_openai_config() -> Dict[str, Any]:
    """Validate OpenAI configuration for LlamaIndex."""
    issues: List[str] = []
    warnings: List[str] = []

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if not api_key:
        issues.append("OPENAI_API_KEY not set")
    elif api_key.startswith("sk-"):
        pass
    else:
        warnings.append("OPENAI_API_KEY format unusual (expected sk-*)")

    if base_url and not base_url.startswith(("https://", "http://")):
        issues.append("OPENAI_BASE_URL must be a valid URL")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_budget_config() -> Dict[str, Any]:
    """Validate budget configuration for guardrails."""
    issues: List[str] = []
    warnings: List[str] = []

    max_tokens = os.getenv("DEFAULT_MAX_TOKENS")
    max_api_calls = os.getenv("DEFAULT_MAX_API_CALLS")
    max_cost_usd = os.getenv("DEFAULT_MAX_COST_USD")

    if max_tokens:
        try:
            tokens = int(max_tokens)
            if tokens <= 0:
                issues.append("DEFAULT_MAX_TOKENS must be positive")
            elif tokens > 10000000:
                warnings.append("DEFAULT_MAX_TOKENS is very large")
        except ValueError:
            issues.append("DEFAULT_MAX_TOKENS must be an integer")
    else:
        warnings.append("DEFAULT_MAX_TOKENS not set (default: 100000)")

    if max_api_calls:
        try:
            calls = int(max_api_calls)
            if calls <= 0:
                issues.append("DEFAULT_MAX_API_CALLS must be positive")
        except ValueError:
            issues.append("DEFAULT_MAX_API_CALLS must be an integer")

    if max_cost_usd:
        try:
            cost = float(max_cost_usd)
            if cost <= 0:
                issues.append("DEFAULT_MAX_COST_USD must be positive")
        except ValueError:
            issues.append("DEFAULT_MAX_COST_USD must be a number")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_dagster_config() -> Dict[str, Any]:
    """Validate Dagster configuration."""
    issues: List[str] = []
    warnings: List[str] = []

    dagster_home = os.getenv("DAGSTER_HOME")
    dagster_postgres_user = os.getenv("DAGSTER_POSTGRES_USER")
    dagster_postgres_password = os.getenv("DAGSTER_POSTGRES_PASSWORD")
    dagster_postgres_db = os.getenv("DAGSTER_POSTGRES_DB")

    if not dagster_home:
        warnings.append("DAGSTER_HOME not set (optional)")

    if dagster_postgres_user and not dagster_postgres_password:
        issues.append("DAGSTER_POSTGRES_USER set but DAGSTER_POSTGRES_PASSWORD not set")

    if dagster_postgres_password and not dagster_postgres_user:
        issues.append("DAGSTER_POSTGRES_PASSWORD set but DAGSTER_POSTGRES_USER not set")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_advanced_config() -> Dict[str, Any]:
    """Validate all advanced integration configurations."""
    results: Dict[str, Any] = {
        "neo4j": validate_neo4j_config(),
        "openai": validate_openai_config(),
        "budget": validate_budget_config(),
        "dagster": validate_dagster_config(),
    }

    all_valid = all(r["valid"] for r in results.values())
    all_issues = []
    all_warnings = []

    for name, result in results.items():
        all_issues.extend([f"{name}: {i}" for i in result["issues"]])
        all_warnings.extend([f"{name}: {w}" for w in result["warnings"]])

    return {
        "valid": all_valid,
        "results": results,
        "issues": all_issues,
        "warnings": all_warnings,
    }


def log_validation_results(results: Dict[str, Any]) -> None:
    """Log validation results."""
    if results["valid"]:
        logger.info("Advanced configuration validation passed")
    else:
        logger.warning(f"Advanced configuration issues: {results['issues']}")

    if results["warnings"]:
        logger.info(f"Advanced configuration warnings: {results['warnings']}")


def setup_default_budget_config() -> None:
    """Set default budget configuration if not set."""
    if not os.getenv("DEFAULT_MAX_TOKENS"):
        os.environ["DEFAULT_MAX_TOKENS"] = "100000"
    if not os.getenv("DEFAULT_MAX_API_CALLS"):
        os.environ["DEFAULT_MAX_API_CALLS"] = "1000"
    if not os.getenv("DEFAULT_MAX_COST_USD"):
        os.environ["DEFAULT_MAX_COST_USD"] = "10.0"
