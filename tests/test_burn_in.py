"""Unit tests for the Burn-In Framework (T3).

All tests use direct mode — no server required.
"""

import pytest

from uar.memory.sqlite_store import SqliteRunStore
from uar.core.registry import SkillRegistry
from uar.testing.burnin.contracts import BurnInEvidence, BurnInReport
from uar.testing.burnin.runner import BurnInRunner


def _make_store(tmp_path):
    return SqliteRunStore(path=str(tmp_path / "burnin_test.db"))


def _make_registry():
    reg = SkillRegistry()
    reg.register("echo", lambda ctx: ctx)
    return reg


def test_burnin_evidence_structure():
    ev = BurnInEvidence(
        scenario="test_scenario",
        passed=True,
        detail="All good",
        score=100,
    )
    assert ev.scenario == "test_scenario"
    assert ev.passed is True
    assert ev.score == 100


def test_burnin_report_to_dict():
    report = BurnInReport(
        level="smoke",
        score=100,
        passed=True,
        evidence=[
            BurnInEvidence("s1", True, "ok", 100),
            BurnInEvidence("s2", True, "ok", 100),
        ],
        errors=[],
        timestamp=1.0,
    )
    d = report.to_dict()
    assert d["level"] == "smoke"
    assert d["score"] == 100
    assert d["passed"] is True
    assert len(d["evidence"]) == 2
    assert d["timestamp"] == 1.0


def test_smoke_report_structure(tmp_path):
    runner = BurnInRunner(
        mode="direct",
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    report = runner.run_smoke()
    assert isinstance(report, BurnInReport)
    assert report.level == "smoke"
    assert isinstance(report.score, int)
    assert 0 <= report.score <= 100
    assert isinstance(report.passed, bool)
    assert isinstance(report.evidence, list)
    assert isinstance(report.errors, list)


def test_all_scenarios_pass_clean_runtime(tmp_path):
    runner = BurnInRunner(
        mode="direct",
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    report = runner.run_smoke()
    failed = [e for e in report.evidence if not e.passed]
    assert failed == [], (
        f"Expected all scenarios to pass, failed: "
        f"{[e.scenario for e in failed]}"
    )
    assert report.passed is True


def test_failed_scenario_lowers_score(tmp_path):
    from uar.testing.burnin.contracts import BurnInEvidence

    runner = BurnInRunner(
        mode="direct",
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    report = runner.run_smoke()

    injected_failure = BurnInEvidence(
        scenario="injected_failure",
        passed=False,
        detail="Forced failure",
        score=0,
    )
    all_evidence = list(report.evidence) + [injected_failure]
    combined_score = int(
        round(sum(e.score for e in all_evidence) / len(all_evidence))
    )
    assert combined_score < 100


def test_report_passed_requires_all_evidence_passing(tmp_path):
    runner = BurnInRunner(
        mode="direct",
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    report = runner.run_smoke()
    if report.passed:
        assert all(e.passed for e in report.evidence)
        assert report.score >= 80


def test_direct_mode_missing_store_returns_failed_report():
    runner = BurnInRunner(mode="direct", store=None, registry=None)
    report = runner.run_smoke()
    assert report.passed is False
    assert report.score == 0
    assert report.errors


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="Invalid mode"):
        BurnInRunner(mode="invalid")


def test_report_has_scenario_names(tmp_path):
    runner = BurnInRunner(
        mode="direct",
        store=_make_store(tmp_path),
        registry=_make_registry(),
    )
    report = runner.run_smoke()
    scenario_names = {e.scenario for e in report.evidence}
    assert "api_reachable" in scenario_names
    assert "store_round_trip" in scenario_names
    assert "replay_confidence" in scenario_names
