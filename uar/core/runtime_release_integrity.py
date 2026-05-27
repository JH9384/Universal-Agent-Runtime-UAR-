from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(slots=True)
class RuntimeReleaseIntegrityReport:
    path: str
    sha256: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "path": self.path,
            "sha256": self.sha256,
        }


class RuntimeReleaseIntegrity:
    def hash_file(self, path: str) -> RuntimeReleaseIntegrityReport:
        payload = Path(path).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()

        return RuntimeReleaseIntegrityReport(
            path=path,
            sha256=digest,
        )
