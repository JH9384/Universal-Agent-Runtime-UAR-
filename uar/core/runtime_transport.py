from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class RuntimeTransportEnvelope:
    """Serializable runtime transport payload.

    This is transport-agnostic so it can back WebSocket, HTTP, file,
    or in-process runtime delivery without coupling core runtime logic
    to a specific server implementation.
    """

    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "payload": dict(self.payload),
            "correlation_id": self.correlation_id,
        }


class RuntimeTransportBuffer:
    def __init__(self) -> None:
        self.envelopes: list[RuntimeTransportEnvelope] = []

    def send(
        self,
        topic: str,
        payload: Dict[str, Any],
        correlation_id: str | None = None,
    ) -> RuntimeTransportEnvelope:
        envelope = RuntimeTransportEnvelope(
            topic=topic,
            payload=dict(payload),
            correlation_id=correlation_id,
        )
        self.envelopes.append(envelope)
        return envelope

    def flush(self) -> list[Dict[str, Any]]:
        return [envelope.to_dict() for envelope in self.envelopes]
