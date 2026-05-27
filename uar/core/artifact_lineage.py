"""Artifact lineage primitives for runtime provenance.

Artifact lineage provides reconstructable ancestry for runtime artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass(slots=True)
class ArtifactLineage:
    artifact_id: str
    parent_run_id: str
    replay_fingerprint: str
    runtime_mode: str
    runtime_version: str = "unknown"
    ancestors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "parent_run_id": self.parent_run_id,
            "replay_fingerprint": self.replay_fingerprint,
            "runtime_mode": self.runtime_mode,
            "runtime_version": self.runtime_version,
            "ancestors": list(self.ancestors),
            "metadata": dict(self.metadata),
        }
