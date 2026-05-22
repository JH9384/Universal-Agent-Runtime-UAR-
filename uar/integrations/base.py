"""Base class for third-party integrations."""

from abc import ABC
from typing import Any


class BaseIntegration(ABC):
    """Minimal base for integration clients."""

    def __init__(self, **config: Any) -> None:
        self.config = config
