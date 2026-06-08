"""Operator metadata entity integrity checks."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from uar.api.state import store


def _decode_entity(raw: Any) -> Dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        try:
            decoded = json.loads(raw)
        except Exception:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def check_metadata_namespace(
    namespace: str,
    *,
    id_field: str = "id",
    sort_field: str = "created_at",
    use_list_meta_keys: bool = True,
    max_index_scan: int = 100,
) -> Dict[str, Any]:
    """Validate metadata entities for one namespace."""
    keys: List[str] = []
    discovery = "bounded_index_scan"

    if use_list_meta_keys and hasattr(store, "list_meta_keys"):
        discovery = "list_meta_keys"
        try:
            keys = [
                key
                for key in store.list_meta_keys()
                if str(key).startswith(f"{namespace}:")
            ]
        except Exception as exc:
            return {
                "namespace": namespace,
                "status": "fail",
                "discovery": discovery,
                "count": 0,
                "corrupt": 0,
                "missing_id": 0,
                "missing_sort_field": 0,
                "duplicate_ids": 0,
                "oldest": None,
                "newest": None,
                "error": str(exc),
            }
    else:
        suffix = namespace.split(":")[-1]
        keys = [f"{namespace}:{suffix}-{i}" for i in range(max_index_scan)]

    count = 0
    corrupt = 0
    missing_id = 0
    missing_sort_field = 0
    duplicate_ids = 0
    ids: Set[str] = set()
    sort_values: List[Any] = []

    for key in keys:
        try:
            raw = store.get_metadata(key)
        except Exception:
            corrupt += 1
            continue

        entity = _decode_entity(raw)
        if entity is None:
            if raw is not None:
                corrupt += 1
            continue

        count += 1

        entity_id = entity.get(id_field)
        if entity_id is None:
            missing_id += 1
        else:
            entity_id_s = str(entity_id)
            if entity_id_s in ids:
                duplicate_ids += 1
            ids.add(entity_id_s)

        sort_value = entity.get(sort_field)
        if sort_value is None:
            missing_sort_field += 1
        else:
            sort_values.append(sort_value)

    status = "ok"
    if corrupt or missing_id or duplicate_ids:
        status = "fail"
    elif missing_sort_field:
        status = "warn"

    return {
        "namespace": namespace,
        "status": status,
        "discovery": discovery,
        "count": count,
        "corrupt": corrupt,
        "missing_id": missing_id,
        "missing_sort_field": missing_sort_field,
        "duplicate_ids": duplicate_ids,
        "oldest": min(sort_values) if sort_values else None,
        "newest": max(sort_values) if sort_values else None,
    }


def check_operator_entity_integrity() -> Dict[str, Any]:
    """Return integrity status for all operator metadata namespaces."""
    namespaces = {
        "snapshots": {
            "namespace": "operator:snapshot",
            "id_field": "timestamp",
            "sort_field": "timestamp",
            "use_list_meta_keys": True,
        },
        "incidents": {
            "namespace": "operator:incident",
            "id_field": "id",
            "sort_field": "created_at",
            "use_list_meta_keys": True,
        },
        "inbox": {
            "namespace": "operator:inbox",
            "id_field": "id",
            "sort_field": "created_at",
            "use_list_meta_keys": False,
            "max_index_scan": 200,
        },
        "investigations": {
            "namespace": "operator:investigation",
            "id_field": "id",
            "sort_field": "started_at",
            "use_list_meta_keys": False,
        },
    }

    results: Dict[str, Any] = {}
    for name, cfg in namespaces.items():
        results[name] = check_metadata_namespace(**cfg)

    statuses = {v.get("status") for v in results.values()}
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"

    return {
        "status": overall,
        "namespaces": results,
    }
