"""Replay certificate primitives.

Provides immutable replay validation artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class ReplayCertificate:
    replay_id: str
    topology_hash: str
    semantic_hash: str
    governance_hash: str

    @property
    def certificate_hash(self) -> str:
        payload = (
            f"{self.replay_id}|"
            f"{self.topology_hash}|"
            f"{self.semantic_hash}|"
            f"{self.governance_hash}"
        )
        return sha256(payload.encode("utf-8")).hexdigest()
