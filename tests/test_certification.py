"""Unit tests for the Certification Engine (T4)."""

from uar.core.certification import certification_level, certify_runtime


class _BurnIn:
    def __init__(self, score=100, passed=True):
        self.score = score
        self.passed = passed


def test_certification_level_gold():
    level = certification_level(
        score=96,
        replay_score=96,
        burnin_passed=True,
        burnin_score=96,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Gold"


def test_certification_level_silver():
    level = certification_level(
        score=85,
        replay_score=85,
        burnin_passed=True,
        burnin_score=70,
        has_violations=False,
        burnin_ran=True,
    )
    assert level == "Silver"


def test_certification_level_experimental():
    level = certification_level(
        score=60,
        replay_score=60,
        burnin_passed=False,
        burnin_score=40,
        has_violations=True,
    )
    assert level == "Experimental"


def test_gold_requires_no_violations():
    level = certification_level(
        score=96,
        replay_score=96,
        burnin_passed=True,
        burnin_score=96,
        has_violations=True,
        burnin_ran=True,
    )
    assert level != "Gold"


def test_gold_requires_burnin_ran():
    level = certification_level(
        score=96,
        replay_score=96,
        burnin_passed=True,
        burnin_score=96,
        has_violations=False,
        burnin_ran=False,
    )
    assert level != "Gold"


def test_gold_requires_burnin_passed():
    level = certification_level(
        score=96,
        replay_score=96,
        burnin_passed=False,
        burnin_score=96,
        has_violations=False,
    )
    assert level != "Gold"


def test_certify_all_perfect():
    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_BurnIn(score=100, passed=True),
        runtime_health_score=100,
    )
    assert report.score == 100
    assert report.level == "Gold"
    assert report.violations == []


def test_certify_missing_burnin_reaches_silver():
    report = certify_runtime(
        replay_confidence_score=90,
        burnin_report=None,
        runtime_health_score=90,
    )
    assert report.level == "Silver", (
        "Strong scores without burn-in should reach Silver"
    )


def test_certify_missing_replay_confidence_adds_violation():
    report = certify_runtime(
        replay_confidence_score=None,
        burnin_report=_BurnIn(score=100, passed=True),
        runtime_health_score=90,
    )
    assert any("replay_confidence" in v for v in report.violations)


def test_certify_weights_are_correct():
    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=_BurnIn(score=100, passed=True),
        runtime_health_score=100,
    )
    assert report.evidence["weights"]["replay_confidence"] == 0.40
    assert report.evidence["weights"]["burnin"] == 0.35
    assert report.evidence["weights"]["runtime_health"] == 0.25
    assert "contract_compliance" not in report.evidence["weights"]


def test_report_to_dict_shape():
    report = certify_runtime(
        replay_confidence_score=80,
        burnin_report=_BurnIn(80, True),
        runtime_health_score=80,
    )
    d = report.to_dict()
    assert "score" in d
    assert "level" in d
    assert "evidence" in d
    assert "violations" in d
    assert "timestamp" in d


def test_certify_low_replay_stays_experimental():
    report = certify_runtime(
        replay_confidence_score=40,
        burnin_report=_BurnIn(score=40, passed=False),
        runtime_health_score=40,
    )
    assert report.level == "Experimental"
    assert report.score < 80


def test_missing_burnin_caps_at_silver_not_gold():
    report = certify_runtime(
        replay_confidence_score=100,
        burnin_report=None,
        runtime_health_score=100,
    )
    assert report.level != "Gold"
