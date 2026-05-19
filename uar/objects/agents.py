"""Capability map for UOR agent endpoints.

The :data:`AGENTS` dict declares which actions each named agent is allowed
to perform. The ``/agents/constraint/check`` endpoint consults this map.
"""

from __future__ import annotations

from typing import Dict, List

AGENTS: Dict[str, List[str]] = {
    "locator": ["query"],
    "verifier": ["verify", "compare"],
    "composer": ["compose"],
    "execution": ["run", "run_object", "run_registered"],
    "runtime_registry": ["register", "list", "get", "seed"],
    "workflow": ["run"],
    "lineage": ["trace"],
    "constraint": ["check"],
    "bridge": ["ingest"],
    "inference": ["analyze"],
    "delegation": ["plan"],
    "atomic_lang_model": ["analyze", "generate", "verify"],
}

__all__ = ["AGENTS"]
