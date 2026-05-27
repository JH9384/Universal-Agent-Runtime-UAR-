from uar.runtime.hardening.operating_modes import (
    OperatingMode,
    choose_mode,
)
from uar.runtime.hardening.pressure_metrics import PressureSnapshot


def test_modes_preserve_replay_identity() -> None:
    decision = choose_mode(
        PressureSnapshot(
            queue_depth=100_000,
            websocket_backlog=100_000,
            propagation_fanout=100_000,
            mutation_rate=1_000_000,
            replay_latency_ms=100_000,
            dropped_events=100_000,
            observer_lag_ms=100_000,
        )
    )

    assert decision.mode is OperatingMode.CORE_ONLY
    assert decision.replay_identity_required is True
    assert decision.event_validity_required is True


def test_modes_reduce_observer_pressure_first() -> None:
    decision = choose_mode(
        PressureSnapshot(websocket_backlog=700, observer_lag_ms=300)
    )

    assert decision.observer_ratio <= 1.0
