"""Tests for Ω-5.4 adaptive confidence module."""

import pytest

from uar.core.adaptive_confidence import (
    MIN_SHOWN_THRESHOLD,
    compute_adaptive_confidence,
    compute_modifier,
    build_quality_stats,
)


class TestComputeModifier:
    def test_insufficient_evidence_returns_1_0(self):
        """Modifier stays at 1.0 when shown count < threshold."""
        mod = compute_modifier(
            shown_count=MIN_SHOWN_THRESHOLD - 1,
            accepted_count=100,
            rejected_count=0,
            dismissed_count=0,
        )
        assert mod == 1.0

    def test_acceptance_80_bump(self):
        """Acceptance rate > 80% gives +0.05 modifier."""
        mod = compute_modifier(
            shown_count=20,
            accepted_count=17,  # 85%
            rejected_count=0,
            dismissed_count=0,
        )
        assert mod == 1.05

    def test_acceptance_90_bump(self):
        """Acceptance rate > 90% gives +0.10 modifier."""
        mod = compute_modifier(
            shown_count=20,
            accepted_count=19,  # 95%
            rejected_count=0,
            dismissed_count=0,
        )
        assert mod == 1.10

    def test_rejection_penalty(self):
        """Rejection rate > 60% gives -0.10 modifier."""
        mod = compute_modifier(
            shown_count=20,
            accepted_count=4,
            rejected_count=14,  # 70%
            dismissed_count=0,
        )
        assert mod == 0.90

    def test_dismissal_penalty(self):
        """Dismissal rate > 70% gives -0.05 modifier."""
        mod = compute_modifier(
            shown_count=20,
            accepted_count=0,
            rejected_count=0,
            dismissed_count=16,  # 80%
        )
        assert mod == 0.95

    def test_combined_signals(self):
        """Multiple signals can combine."""
        mod = compute_modifier(
            shown_count=20,
            accepted_count=19,  # 95% → +0.10
            rejected_count=13,  # 65% → -0.10
            dismissed_count=0,
        )
        assert mod == 1.0

    def test_clamp_max(self):
        """Modifier caps at 1.5 (not reachable with current rules alone)."""
        # With current rules the practical max is 1.10
        mod = compute_modifier(
            shown_count=100,
            accepted_count=100,
            rejected_count=0,
            dismissed_count=0,
        )
        assert mod == 1.10

    def test_clamp_min(self):
        """Modifier floors at 0.5 (not reachable with current rules alone)."""
        # With current rules the practical min is ~0.85
        mod = compute_modifier(
            shown_count=100,
            accepted_count=0,
            rejected_count=70,  # 70%
            dismissed_count=80,  # 80%
        )
        assert mod == pytest.approx(0.85, abs=0.01)


class TestComputeAdaptiveConfidence:
    def test_no_evidence_returns_base(self):
        """Without enough evidence, adaptive confidence == base confidence."""
        conf = compute_adaptive_confidence(
            base_confidence=0.80,
            shown_count=MIN_SHOWN_THRESHOLD - 1,
            accepted_count=0,
            rejected_count=0,
            dismissed_count=0,
        )
        assert conf == 0.80

    def test_high_acceptance_boosts_confidence(self):
        conf = compute_adaptive_confidence(
            base_confidence=0.80,
            shown_count=20,
            accepted_count=19,
            rejected_count=0,
            dismissed_count=0,
        )
        assert conf == pytest.approx(0.88, abs=0.01)


class TestBuildQualityStats:
    def test_empty_returns_empty(self):
        stats = build_quality_stats([], [])
        assert stats == {}

    def test_shown_and_feedback_aggregated(self):
        shown = [
            {"recommendation_id": "abc", "user_id": "u1"},
            {"recommendation_id": "abc", "user_id": "u1"},
            {"recommendation_id": "def", "user_id": "u1"},
        ]
        feedback = [
            {"recommendation_id": "abc", "action": "accept"},
            {"recommendation_id": "abc", "action": "accept"},
            {"recommendation_id": "abc", "action": "reject"},
        ]
        stats = build_quality_stats(shown, feedback)
        assert stats["abc"]["shown_count"] == 2
        assert stats["abc"]["accepted_count"] == 2
        assert stats["abc"]["rejected_count"] == 1
        assert stats["def"]["shown_count"] == 1
        assert stats["def"]["accepted_count"] == 0
