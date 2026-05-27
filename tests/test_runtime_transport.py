from uar.core.runtime_transport import RuntimeTransportBuffer


def test_runtime_transport_flush():
    transport = RuntimeTransportBuffer()

    transport.send(
        topic="runtime.replay",
        payload={"replay_id": "r-001"},
        correlation_id="corr-001",
    )

    payload = transport.flush()

    assert len(payload) == 1
    assert payload[0]["topic"] == "runtime.replay"
    assert payload[0]["correlation_id"] == "corr-001"
