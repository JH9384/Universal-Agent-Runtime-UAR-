"""RuntimeEvent schema compatibility matrix.

RuntimeEvent schemas are operational replay contracts.
Changes must be explicit, versioned, and replay-aware.
"""

from __future__ import annotations

from typing import Dict, Set

CURRENT_EVENT_SCHEMA = "uar.event.v1"


# Compatibility graph.
# Future migrations should update this intentionally.
EVENT_SCHEMA_COMPATIBILITY: Dict[str, Set[str]] = {
    "uar.event.v1": {
        "uar.event.v1",
    },
}


def is_schema_compatible(
    source_schema: str,
    target_schema: str = CURRENT_EVENT_SCHEMA,
) -> bool:
    """Return whether RuntimeEvent schemas are replay-compatible."""
    allowed = EVENT_SCHEMA_COMPATIBILITY.get(source_schema, set())
    return target_schema in allowed


def require_schema_compatibility(
    source_schema: str,
    target_schema: str = CURRENT_EVENT_SCHEMA,
) -> None:
    """Raise if RuntimeEvent schemas are incompatible."""
    if not is_schema_compatible(source_schema, target_schema):
        raise RuntimeError(
            f"Incompatible RuntimeEvent schema transition: "
            f"{source_schema} -> {target_schema}"
        )
