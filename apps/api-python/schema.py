from __future__ import annotations

from typing import Any

from fastapi import HTTPException

REQUIRED_OBJECT_FIELDS = {"mediaType", "mode", "attributes", "links", "content"}
RUNTIME_REQUIRED_ATTRS = {"schema", "type", "runtimeName"}


def validate_object_envelope(obj: dict[str, Any]) -> None:
    """Validate the minimum UAR/UOR-aligned object envelope.

    This is intentionally lightweight in Phase 2. It is safe to import without
    changing main.py behavior until endpoint wiring is explicitly performed in a
    later phase.
    """
    missing = REQUIRED_OBJECT_FIELDS.difference(obj.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"Object missing required fields: {sorted(missing)}")

    attributes = obj.get("attributes") or {}
    if not isinstance(attributes, dict):
        raise HTTPException(status_code=400, detail="Object.attributes must be a mapping")

    if "schema" not in attributes:
        raise HTTPException(status_code=400, detail="Object.attributes.schema is required for UOR alignment")

    if not isinstance(obj.get("links"), list):
        raise HTTPException(status_code=400, detail="Object.links must be a list")

    obj_type = attributes.get("type")
    if obj_type is not None and not isinstance(obj_type, str):
        raise HTTPException(status_code=400, detail="Object.attributes.type must be a string if provided")


def validate_runtime_attributes(attributes: dict[str, Any]) -> None:
    missing = RUNTIME_REQUIRED_ATTRS.difference(attributes.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"Runtime missing required attributes: {sorted(missing)}")


def validate_links(links: list[dict[str, Any]]) -> None:
    for link in links:
        if "rel" not in link or "target" not in link:
            raise HTTPException(status_code=400, detail="Links must include rel and target")
