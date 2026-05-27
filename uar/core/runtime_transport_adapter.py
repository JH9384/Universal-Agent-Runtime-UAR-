from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol

from .runtime_transport import RuntimeTransportEnvelope


class RuntimeTransportSink(Protocol):
    def send(self, envelope: RuntimeTransportEnvelope) -> None:
        ...


@dataclass(slots=True)
class InMemoryRuntimeTransportSink:
    sent: list[RuntimeTransportEnvelope] = field(default_factory=list)

    def send(self, envelope: RuntimeTransportEnvelope) -> None:
        self.sent.append(envelope)

    def snapshot(self) -> list[Dict[str, Any]]:
        return [envelope.to_dict() for envelope in self.sent]


class RuntimeTransportAdapter:
    def __init__(self, sink: RuntimeTransportSink) -> None:
        self.sink = sink

    def publish(self, envelope: RuntimeTransportEnvelope) -> None:
        self.sink.send(envelope)
