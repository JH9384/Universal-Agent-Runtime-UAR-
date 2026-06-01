"""Tests for trust-weighted ranking module (Omega-7b)."""

from uar.core.operational_learning import Recommendation
from uar.core.trust_ranking import (
    attach_trust_to_recommendations,
    compute_blend,
    sort_by_blend,
)


class TestComputeBlend:
    def test_high_confidence_low_trust(self):
        """0.90 * 0.7 + 0.50 * 0.3 = 0.78 — gentler than product (0.45)."""
        assert round(compute_blend(0.90, 0.50), 2) == 0.78

    def test_perfect_scores(self):
        assert compute_blend(1.0, 1.0) == 1.0

    def test_zero_trust(self):
        assert round(compute_blend(0.80, 0.0), 2) == 0.56

    def test_zero_confidence(self):
        # 0.7 * 0 + 0.3 * 0.8 = 0.24
        assert round(compute_blend(0.0, 0.80), 2) == 0.24

    def test_clamped_to_zero(self):
        assert compute_blend(0.0, -0.5) == 0.0

    def test_clamped_to_one(self):
        assert compute_blend(1.0, 1.0) == 1.0

    def test_mid_values(self):
        assert round(compute_blend(0.5, 0.5), 2) == 0.50


class TestAttachTrustToRecommendations:
    def test_maps_by_category(self):
        recs = [
            Recommendation(
                category="remediate",
                priority="high",
                confidence=0.9,
                title="Fix A",
                description="Desc A",
                source="test",
            ),
            Recommendation(
                category="investigate",
                priority="medium",
                confidence=0.7,
                title="Look into B",
                description="Desc B",
                source="test",
            ),
        ]
        trust_result = {
            "recommendation_types": [
                {"type": "remediate", "trust_score": 0.85},
                {"type": "investigate", "trust_score": 0.30},
            ]
        }
        attach_trust_to_recommendations(recs, trust_result)
        assert recs[0].trust_score == 0.85
        assert recs[1].trust_score == 0.30

    def test_unknown_category_defaults_to_zero(self):
        rec = Recommendation(
            category="unknown",
            priority="low",
            confidence=0.5,
            title="X",
            description="D",
            source="test",
        )
        trust_result = {
            "recommendation_types": [
                {"type": "remediate", "trust_score": 0.85},
            ]
        }
        attach_trust_to_recommendations([rec], trust_result)
        assert rec.trust_score == 0.0

    def test_empty_trust_result(self):
        rec = Recommendation(
            category="remediate",
            priority="high",
            confidence=0.9,
            title="X",
            description="D",
            source="test",
        )
        attach_trust_to_recommendations([rec], {})
        assert rec.trust_score == 0.0


class TestSortByBlend:
    def test_priority_preserved_within_blend(self):
        """Critical still wins over high, even with lower blend."""
        recs = [
            Recommendation(
                category="remediate",
                priority="high",
                confidence=0.95,
                title="High priority",
                description="D",
                source="test",
                trust_score=0.0,  # blend = 0.665
            ),
            Recommendation(
                category="remediate",
                priority="critical",
                confidence=0.60,
                title="Critical priority",
                description="D",
                source="test",
                trust_score=0.0,  # blend = 0.42
            ),
        ]
        sort_by_blend(recs)
        assert recs[0].priority == "critical"
        assert recs[1].priority == "high"

    def test_blend_changes_order_within_same_priority(self):
        """Within same priority, higher blend wins."""
        recs = [
            Recommendation(
                category="remediate",
                priority="high",
                confidence=0.80,
                title="Low trust",
                description="D",
                source="test",
                trust_score=0.0,  # blend = 0.56
            ),
            Recommendation(
                category="investigate",
                priority="high",
                confidence=0.60,
                title="High trust",
                description="D",
                source="test",
                trust_score=1.0,  # blend = 0.72
            ),
        ]
        sort_by_blend(recs)
        assert recs[0].title == "High trust"
        assert recs[1].title == "Low trust"

    def test_confidence_is_preserved_not_mutated(self):
        """sort_by_blend must NOT overwrite rec.confidence.

        Calibration metadata and the UI depend on the original value.
        """
        rec = Recommendation(
            category="remediate",
            priority="high",
            confidence=0.80,
            title="X",
            description="D",
            source="test",
            trust_score=0.50,
        )
        sort_by_blend([rec])
        # Original confidence intact
        assert round(rec.confidence, 2) == 0.80
        # Blend stored on temporary attribute
        assert round(rec._blend_score, 2) == 0.71  # 0.7*0.8 + 0.3*0.5
