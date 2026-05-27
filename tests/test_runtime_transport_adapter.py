from uar.core.runtime_transport import RuntimeTransportEnvelope
from uar.core.runtime_transport_adapter import (
    InMemoryRuntimeTransportSink,
    RuntimeTransportAdapter,
)


def test_runtime_transport_adapter_routes_envelope():
    sink = InMemoryRuntimeTransportSink()
    adapter = RuntimeTransportAdapter(sink=sink)

    adapter.publish(
        RuntimeTransportEnvelope(
            topic="runtime.health",
            payload={"ok": True},
            correlation_id="health-001",
        )
    )

    snapshot = sink.snapshot()

    assert len(snapshot) == 1
    assert snapshot[0]["topic"] == "runtime.health"
