from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ReplaySyncPacket:
    source_identity: str
    target_identity: str
    replay_ids: List[str] = field(default_factory=list)
    checkpoint_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "source_identity": self.source_identity,
            "target_identity": self.target_identity,
            "replay_ids": list(self.replay_ids),
            "checkpoint_ids": list(self.checkpoint_ids),
        }


class ReplaySynchronizer:
    def build_packet(
        self,
        source_identity: str,
        target_identity: str,
        replay_ids: List[str],
        checkpoint_ids: List[str],
    ) -> ReplaySyncPacket:
        return ReplaySyncPacket(
            source_identity=source_identity,
            target_identity=target_identity,
            replay_ids=list(replay_ids),
            checkpoint_ids=list(checkpoint_ids),
        )
