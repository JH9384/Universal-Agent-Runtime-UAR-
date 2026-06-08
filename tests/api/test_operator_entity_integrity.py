"""Operator entity integrity checker tests."""

from unittest.mock import MagicMock


def test_entity_integrity_reports_clean_snapshot_namespace(monkeypatch):
    import uar.api.routers.operator.checkers.entity_integrity as integrity

    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = [
        "operator:snapshot:100",
        "operator:snapshot:200",
    ]
    fake_store.get_metadata.side_effect = lambda key: {
        "operator:snapshot:100": {"timestamp": 100},
        "operator:snapshot:200": {"timestamp": 200},
    }[key]
    monkeypatch.setattr(integrity, "store", fake_store)

    result = integrity.check_metadata_namespace(
        "operator:snapshot",
        id_field="timestamp",
        sort_field="timestamp",
        use_list_meta_keys=True,
    )

    assert result["status"] == "ok"
    assert result["count"] == 2
    assert result["oldest"] == 100
    assert result["newest"] == 200


def test_entity_integrity_detects_corrupt_payload(monkeypatch):
    import uar.api.routers.operator.checkers.entity_integrity as integrity

    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = ["operator:snapshot:bad"]
    fake_store.get_metadata.return_value = "not-json"
    monkeypatch.setattr(integrity, "store", fake_store)

    result = integrity.check_metadata_namespace(
        "operator:snapshot",
        id_field="timestamp",
        sort_field="timestamp",
        use_list_meta_keys=True,
    )

    assert result["status"] == "fail"
    assert result["corrupt"] == 1


def test_entity_integrity_detects_missing_sort_field(monkeypatch):
    import uar.api.routers.operator.checkers.entity_integrity as integrity

    fake_store = MagicMock()
    fake_store.list_meta_keys.return_value = ["operator:snapshot:1"]
    fake_store.get_metadata.return_value = {"timestamp": 1}
    monkeypatch.setattr(integrity, "store", fake_store)

    result = integrity.check_metadata_namespace(
        "operator:snapshot",
        id_field="timestamp",
        sort_field="created_at",
        use_list_meta_keys=True,
    )

    assert result["status"] == "warn"
    assert result["missing_sort_field"] == 1


def test_entity_integrity_endpoint_route_exists():
    from uar.api.routers.operator import time_machine

    paths = {getattr(route, "path", "") for route in time_machine.router.routes}
    assert "/api/uar/operator/entity-integrity" in paths
