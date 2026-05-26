from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class RuntimeMigration:
    migration_id: str
    source_version: str
    target_version: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "migration_id": self.migration_id,
            "source_version": self.source_version,
            "target_version": self.target_version,
        }
