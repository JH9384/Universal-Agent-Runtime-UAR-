"""Operator metadata entity retention health tests."""

from unittest.mock import MagicMock


def test_entity_retention_health_reports_backend_capabilities(monkeypatch):
    import uar.api.routers.operator.common as common
    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = []
    fake_store.delete_metadata = MagicMock()
    monkeypatch.setattr(common, "store", fake_store)
    health = common._entity_retention_health()
    assert health["metadata_backend"]["list_meta_keys"] is True
    assert health["metadata_backend"]["delete_metadata"] is True
    assert health["entities"]["snapshots"]["namespace"] == "operator:snapshot"
    assert health["entities"]["snapshots"]["retention_capable"] is True


def test_entity_retention_health_endpoint_route_exists():
    from uar.api.routers.operator import time_machine
    paths = {getattr(route, "path", "") for route in time_machine.router.routes}
    assert "/api/uar/operator/entity-health" in paths
