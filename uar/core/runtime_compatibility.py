from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class RuntimeCompatibilityReport:
    current_version: str
    target_version: str
    compatible: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "current_version": self.current_version,
            "target_version": self.target_version,
            "compatible": self.compatible,
        }


class RuntimeCompatibilityChecker:
    def check(self, current_version: str, target_version: str) -> RuntimeCompatibilityReport:
        compatible = current_version.split('.')[0] == target_version.split('.')[0]

        return RuntimeCompatibilityReport(
            current_version=current_version,
            target_version=target_version,
            compatible=compatible,
        )
