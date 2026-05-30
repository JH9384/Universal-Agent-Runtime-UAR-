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


def test_observer_sampled_mode() -> None:
    """Score in [0.35, 0.55) triggers OBSERVER_SAMPLED."""
    decision = choose_mode(
        PressureSnapshot(
            queue_depth=1000,
            websocket_backlog=1000,
            propagation_fanout=500,
        )
    )
    assert decision.mode.value == "observer_sampled"


def test_observer_reduced_mode() -> None:
    """Score in [0.55, 0.75) triggers OBSERVER_REDUCED."""
    decision = choose_mode(
        PressureSnapshot(
            queue_depth=1000,
            websocket_backlog=1000,
            propagation_fanout=500,
            mutation_rate=10_000,
        )
    )
    assert decision.mode.value == "observer_reduced"


def test_trace_compact_mode() -> None:
    """Score in [0.75, 0.9) triggers TRACE_COMPACT."""
    decision = choose_mode(
        PressureSnapshot(
            queue_depth=1000,
            websocket_backlog=1000,
            propagation_fanout=500,
            mutation_rate=10_000,
            replay_latency_ms=5000,
            dropped_events=500,
        )
    )
    assert decision.mode.value == "trace_compact"
