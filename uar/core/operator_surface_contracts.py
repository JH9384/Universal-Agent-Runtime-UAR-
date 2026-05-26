from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class OperatorSurfaceCard:
    title: str
    category: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "payload": dict(self.payload),
        }


@dataclass(slots=True)
class OperatorSurfaceSnapshot:
    runtime_version: str
    cards: List[OperatorSurfaceCard] = field(default_factory=list)

    def add_card(self, card: OperatorSurfaceCard) -> None:
        self.cards.append(card)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "cards": [card.to_dict() for card in self.cards],
        }
