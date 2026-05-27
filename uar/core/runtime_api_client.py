from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from urllib.request import urlopen
import json


@dataclass(slots=True)
class RuntimeApiClient:
    base_url: str = 'http://127.0.0.1:8080'

    def health(self) -> Dict[str, object]:
        with urlopen(f'{self.base_url}/health') as response:
            return json.loads(response.read().decode('utf-8'))

    def telemetry(self) -> Dict[str, object] | list[Dict[str, object]]:
        with urlopen(f'{self.base_url}/telemetry') as response:
            return json.loads(response.read().decode('utf-8'))
