from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class SemanticReplayRecord:
    replay_id: str
    canonical_form: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "replay_id": self.replay_id,
            "canonical_form": self.canonical_form,
        }


class SemanticReplayNormalizer:
    def normalize(self, content: str) -> str:
        return " ".join(content.strip().lower().split())
