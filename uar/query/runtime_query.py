from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class RuntimeQuery:
    category: str
    filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "filters": dict(self.filters),
        }


@dataclass(slots=True)
class RuntimeQueryResult:
    category: str
    results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "results": list(self.results),
        }


class RuntimeQueryEngine:
    def query(self, query: RuntimeQuery, records: List[Dict[str, Any]]) -> RuntimeQueryResult:
        results = []
        for record in records:
            if record.get("category") != query.category:
                continue
            if all(record.get(key) == value for key, value in query.filters.items()):
                results.append(dict(record))

        return RuntimeQueryResult(category=query.category, results=results)
