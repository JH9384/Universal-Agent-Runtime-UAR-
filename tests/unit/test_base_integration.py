"""Tests for uar.integrations.base."""

from uar.integrations.base import BaseIntegration


def test_base_integration_stores_config():
    """BaseIntegration must store config dict."""
    integration = BaseIntegration(api_key="secret")
    assert integration.config == {"api_key": "secret"}


def test_base_integration_empty_config():
    """BaseIntegration must accept empty config."""
    integration = BaseIntegration()
    assert integration.config == {}
