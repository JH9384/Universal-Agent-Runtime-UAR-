from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ContinuitySearchResult:
    query: str
    matches: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "query": self.query,
            "matches": list(self.matches),
        }


class ContinuitySearchEngine:
    def search(self, query: str, candidates: List[str]) -> ContinuitySearchResult:
        matches = [candidate for candidate in candidates if query.lower() in candidate.lower()]
        return ContinuitySearchResult(query=query, matches=matches)
