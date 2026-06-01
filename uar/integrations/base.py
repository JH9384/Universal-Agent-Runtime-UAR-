"""Base class for third-party integrations."""

from typing import Any


class BaseIntegration:
    """Minimal base for integration clients."""

    def __init__(self, **config: Any) -> None:
        self.config = config
