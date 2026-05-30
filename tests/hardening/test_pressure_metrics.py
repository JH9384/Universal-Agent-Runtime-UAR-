"""Tests for uar.runtime.hardening.pressure_metrics."""

from uar.runtime.hardening.pressure_metrics import (
    EquilibriumSnapshot,
    PressureLedger,
    PressureSnapshot,
)


class TestPressureSnapshot:
    def test_pressure_score_zero(self):
        snap = PressureSnapshot()
        assert snap.pressure_score() == 0.0

    def test_pressure_score_clamped(self):
        snap = PressureSnapshot(
            queue_depth=1_000_000,
            websocket_backlog=1_000_000,
            propagation_fanout=1_000_000,
            mutation_rate=1_000_000,
            replay_latency_ms=1_000_000,
            dropped_events=1_000_000,
            observer_lag_ms=1_000_000,
        )
        assert snap.pressure_score() == 1.0


class TestEquilibriumSnapshot:
    def test_is_stable_true(self):
        eq = EquilibriumSnapshot(
            pressure=PressureSnapshot(),
            convergence_score=0.9,
            oscillation_score=0.1,
            stabilization_latency_ms=0.0,
        )
        assert eq.is_stable() is True

    def test_is_stable_false_low_convergence(self):
        eq = EquilibriumSnapshot(
            pressure=PressureSnapshot(),
            convergence_score=0.5,
            oscillation_score=0.1,
            stabilization_latency_ms=0.0,
        )
        assert eq.is_stable() is False


class TestPressureLedger:
    def test_record_and_latest(self):
        ledger = PressureLedger()
        snap = PressureSnapshot(queue_depth=10)
        ledger.record(snap)
        assert ledger.latest() == snap

    def test_latest_empty(self):
        ledger = PressureLedger()
        assert ledger.latest() is None

    def test_max_pressure_empty(self):
        ledger = PressureLedger()
        assert ledger.max_pressure() == 0.0

    def test_max_pressure(self):
        ledger = PressureLedger()
        ledger.record(PressureSnapshot(queue_depth=100))
        ledger.record(PressureSnapshot(queue_depth=500))
        assert ledger.max_pressure() > 0.0

    def test_summarize_empty(self):
        ledger = PressureLedger()
        summary = ledger.summarize()
        assert summary["sample_count"] == 0
        assert summary["latest_pressure"] == 0.0

    def test_summarize(self):
        ledger = PressureLedger()
        ledger.record(PressureSnapshot(queue_depth=100))
        summary = ledger.summarize()
        assert summary["sample_count"] == 1
        assert summary["dropped_events"] == 0
