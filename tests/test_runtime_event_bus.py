from uar.core.runtime_event_bus import RuntimeEventBus


def test_runtime_event_bus_publish_and_query():
    bus = RuntimeEventBus()

    bus.publish(
        topic="runtime.health",
        category="runtime",
        payload={"ok": True},
    )

    snapshot = bus.snapshot()
    runtime_events = bus.by_category("runtime")

    assert len(snapshot) == 1
    assert len(runtime_events) == 1
    assert runtime_events[0]["payload"]["ok"] is True
