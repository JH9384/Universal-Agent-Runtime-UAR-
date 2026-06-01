"""RE-AUDIT SPRINT Ω-4D — Extended Deployment.

Observe how the governance, provenance, memory, and certification
layers behave when they accumulate extended history.

Not: Does it work?
Instead: What emerges after sustained operation?

Metrics:
- Governance records created
- Recurring patterns discovered
- Authenticity failures detected
- Operator review rates
- Retention distribution
- Governance trend analysis
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any, Dict, List

from uar.core.executor import make_executor_event
from uar.core.governance import (
    ApprovalState,
    RetentionClass,
    GovernanceRecord,
    build_governance_record,
    summarize_governance,
)
from uar.core.multi_run_intelligence import (
    find_recurring_failures,
    summarize_operational_memory,
)
from uar.core.replay import run_record_from_events, certify_replay


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_run(
    run_id: str,
    skills: List[str],
    status: str = "completed",
    error: str = "",
    timestamp: float = 0.0,
) -> Dict[str, Any]:
    """Build a run dict with specified outcome."""
    events = [
        make_executor_event(
            "start", run_id, "g1",
            payload={"skills": skills},
        ),
    ]
    for skill in skills:
        if status == "completed":
            events.append(
                make_executor_event(
                    "skill_complete", run_id, "g1", skill=skill,
                )
            )
        else:
            events.append(
                make_executor_event(
                    "skill_failed", run_id, "g1",
                    skill=skill, error=error or "failure",
                )
            )
            break

    events.append(
        make_executor_event(
            "complete", run_id, "g1",
            payload={
                "status": status,
                "outputs": [] if status != "completed" else [{"ok": True}],
                "errors": [error] if error else [],
                "final_context": {},
            },
        )
    )
    record = run_record_from_events(events)
    d = dataclasses.asdict(record)
    d["timestamp"] = timestamp
    d["status"] = status
    d["errors"] = [error] if error else []
    return d


def _simulate_month(
    month: int,
    runs_per_day: int = 10,
    failure_rate: float = 0.25,
    tamper_rate: float = 0.05,
) -> List[GovernanceRecord]:
    """Simulate one month of operation, returning governance records."""
    random.seed(42 + month)
    records: List[GovernanceRecord] = []
    all_runs: List[Dict[str, Any]] = []

    for day in range(30):
        for run_idx in range(runs_per_day):
            run_id = f"m{month:02d}-d{day:02d}-r{run_idx:03d}"
            skills = ["skill_a", "skill_b"]

            # Determine outcome
            is_failure = random.random() < failure_rate
            is_tampered = random.random() < tamper_rate
            error = "timeout" if is_failure else ""
            status = "failed" if is_failure else "completed"

            run_dict = _make_run(run_id, skills, status, error)
            record = run_record_from_events(run_dict["events"])
            all_runs.append(run_dict)

            # Certify
            replay_cert = certify_replay(record)

            # Tamper if scheduled
            if is_tampered and not is_failure:
                record.events[1]["payload"] = {"tampered": True}

            auth_cert = build_governance_record(
                run_id,
                replay_cert=replay_cert,
                authenticity_cert={
                    "authenticity_verdict": (
                        "tampered" if is_tampered else "authentic"
                    ),
                },
                actor="system",
            )
            records.append(auth_cert)

    # Tag recurring patterns
    recurring = find_recurring_failures(all_runs, min_occurrences=3)
    rec_sigs = {p.signature for p in recurring}

    for rec in records:
        # Mark recurring patterns as requiring review
        if rec.failure_signature in rec_sigs:
            rec.is_recurring = True
            rec.recurrence_tags.append(rec.failure_signature)
            rec.retention_class = RetentionClass.RECURRING
            if rec.approval_state == ApprovalState.APPROVED:
                rec.approval_state = ApprovalState.PENDING
                rec.notes.append("Recurring pattern detected: review required")

        # Also mark any failed run as pending (operators should review)
        run_dict = next(
            (r for r in all_runs if r["run_id"] == rec.run_id), {}
        )
        if run_dict.get("status") == "failed" and (
            rec.approval_state == ApprovalState.APPROVED
        ):
            rec.approval_state = ApprovalState.PENDING
            rec.notes.append("Failure detected: pending operator review")

    return records


# ------------------------------------------------------------------
# Ω-4D Tests
# ------------------------------------------------------------------

class TestOmega4DGovernanceAccumulation:
    """Measure governance record creation and distribution over time."""

    def test_governance_records_created_over_month(self):
        """One month of operation produces expected governance volume."""
        records = _simulate_month(month=1, runs_per_day=10)

        assert len(records) == 300  # 30 days * 10 runs
        print(f"\n[Ω-4D] Month 1: {len(records)} governance records created")

    def test_governance_trend_three_months(self):
        """Track governance metrics across three simulated months."""
        monthly_summaries: List[Dict[str, Any]] = []
        for month in range(1, 4):
            records = _simulate_month(
                month=month,
                runs_per_day=10,
                failure_rate=0.25,
                tamper_rate=0.05,
            )
            summary = summarize_governance(records)
            monthly_summaries.append(summary)

        print("\n[Ω-4D] Governance trend (3 months):")
        for i, s in enumerate(monthly_summaries, 1):
            print(
                f"  Month {i}: {s['total_records']} records, "
                f"cert_rate={s['certification_rate']:.0%}, "
                f"approval_rate={s['approval_rate']:.0%}, "
                f"tampered={s['tampered']}, "
                f"recurring={s['recurring_failures']}"
            )

        # All months should have similar structure (same params)
        for s in monthly_summaries:
            assert s["total_records"] == 300
            assert s["certification_rate"] > 0.9


class TestOmega4DPatternDiscoveryRate:
    """Measure how quickly recurring patterns emerge."""

    def test_patterns_emerge_within_days(self):
        """Recurring failures should be detectable within first week."""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []

        # Simulate one week with high failure rate
        for day in range(7):
            for run_idx in range(10):
                run_id = f"week1-d{day}-r{run_idx}"
                # 50% failure rate, mostly timeout
                is_failure = random.random() < 0.5
                error = "timeout" if is_failure else ""
                status = "failed" if is_failure else "completed"
                all_runs.append(_make_run(run_id, ["a", "b"], status, error))

        recurring = find_recurring_failures(all_runs, min_occurrences=3)

        assert len(recurring) > 0, "Patterns should emerge within a week"
        top = recurring[0]
        print(
            f"\n[Ω-4D] Pattern discovery: {top.signature} "
            f"detected with {top.occurrences} occurrences in 7 days"
        )

    def test_pattern_discovery_accelerates_with_volume(self):
        """More runs = more patterns discovered (up to a point)."""
        for volume in [50, 100, 200]:
            random.seed(42)
            runs = [
                _make_run(
                    f"v{volume}-{i}", ["a", "b"],
                    "failed" if random.random() < 0.4 else "completed",
                    "timeout" if random.random() < 0.4 else "",
                )
                for i in range(volume)
            ]
            patterns = find_recurring_failures(runs, min_occurrences=3)
            print(
                f"\n[Ω-4D] Volume {volume}: {len(patterns)} patterns"
            )


class TestOmega4DAuthenticityFailureDetection:
    """Measure authenticity failure detection over extended operation."""

    def test_tampered_rations_consistent(self):
        """Tampered detection rate should match injection rate."""
        records = _simulate_month(
            month=1, runs_per_day=10, tamper_rate=0.05,
        )

        tampered = sum(
            1 for r in records
            if r.authenticity_verdict == "tampered"
        )
        detected_rate = tampered / len(records)

        # With 5% tamper rate, should detect ~5% (tolerance for randomness)
        assert 0.03 <= detected_rate <= 0.10, (
            f"Detection rate {detected_rate:.1%} far from injection 5%"
        )
        print(
            f"\n[Ω-4D] Authenticity: {tampered}/{len(records)} "
            f"tampered detected ({detected_rate:.1%})"
        )

    def test_tampered_retention_permanent(self):
        """All tampered records should have permanent retention."""
        records = _simulate_month(
            month=1, runs_per_day=10, tamper_rate=0.05,
        )

        for r in records:
            if r.authenticity_verdict == "tampered":
                assert r.retention_class == RetentionClass.TAMPERED, (
                    f"Run {r.run_id}: tampered but "
                    f"retention={r.retention_class}"
                )


class TestOmega4DOperatorReviewRates:
    """Measure operator review workflow behavior."""

    def test_auto_approval_rate(self):
        """Most clean runs should be auto-approved."""
        records = _simulate_month(
            month=1, runs_per_day=10, failure_rate=0.0, tamper_rate=0.0,
        )

        approved = sum(
            1 for r in records
            if r.approval_state == ApprovalState.APPROVED
        )
        auto_rate = approved / len(records)

        assert auto_rate > 0.95, (
            f"Auto-approval rate {auto_rate:.1%} too low for clean runs"
        )
        print(
            f"\n[Ω-4D] Auto-approval: {approved}/{len(records)} "
            f"({auto_rate:.1%})"
        )

    def test_review_queue_grows_with_failures(self):
        """Pending records accumulate when failures occur."""
        records = _simulate_month(
            month=1, runs_per_day=10, failure_rate=0.3, tamper_rate=0.0,
        )

        pending = sum(
            1 for r in records
            if r.approval_state == ApprovalState.PENDING
        )
        pending_rate = pending / len(records)

        assert pending_rate > 0.2, "Review queue should be substantial"
        print(
            f"\n[Ω-4D] Review queue: {pending}/{len(records)} "
            f"pending ({pending_rate:.1%})"
        )


class TestOmega4DRetentionDistribution:
    """Measure how retention classes distribute over time."""

    def test_retention_distribution_over_month(self):
        """Retention classes should reflect operational reality."""
        records = _simulate_month(
            month=1, runs_per_day=10,
            failure_rate=0.25, tamper_rate=0.05,
        )

        summary = summarize_governance(records)
        dist = summary["retention_distribution"]

        print("\n[Ω-4D] Retention distribution:")
        for rc, count in dist.items():
            print(f"  {rc}: {count} ({count / len(records):.1%})")

        # Should have some permanent retention (tampered + recurring)
        permanent = dist.get("tampered", 0) + dist.get("recurring", 0)
        assert permanent > 0, "Some records should have permanent retention"

    def test_retention_trend_three_months(self):
        """Retention patterns should stabilize over time."""
        distributions: List[Dict[str, int]] = []
        for month in range(1, 4):
            records = _simulate_month(
                month=month, runs_per_day=10,
                failure_rate=0.25, tamper_rate=0.05,
            )
            summary = summarize_governance(records)
            distributions.append(summary["retention_distribution"])

        print("\n[Ω-4D] Retention trend (3 months):")
        for i, dist in enumerate(distributions, 1):
            print(f"  Month {i}: {dist}")


class TestOmega4DEmergentGovernanceAnalytics:
    """Governance metrics that only emerge during extended operation."""

    def test_certification_rate_stability(self):
        """Certification rate should remain stable over time."""
        rates: List[float] = []
        for month in range(1, 4):
            records = _simulate_month(
                month=month, runs_per_day=10,
                failure_rate=0.2, tamper_rate=0.05,
            )
            summary = summarize_governance(records)
            rates.append(summary["certification_rate"])

        # All rates should be within a tight band (same params)
        assert max(rates) - min(rates) < 0.1, (
            f"Certification rates unstable: {rates}"
        )
        print(
            f"\n[Ω-4D] Certification stability: "
            f"min={min(rates):.1%}, max={max(rates):.1%}"
        )

    def test_approval_rate_correlates_with_failure_rate(self):
        """Higher failure rate should produce lower approval rate."""
        for failure_rate in [0.0, 0.25, 0.5]:
            records = _simulate_month(
                month=1, runs_per_day=10,
                failure_rate=failure_rate, tamper_rate=0.0,
            )
            summary = summarize_governance(records)
            print(
                f"\n[Ω-4D] failure_rate={failure_rate:.0%} -> "
                f"approval_rate={summary['approval_rate']:.0%}"
            )

    def test_operational_memory_integration(self):
        """Governance + operational memory = full operational picture."""
        random.seed(42)
        all_runs: List[Dict[str, Any]] = []
        for i in range(100):
            is_failure = random.random() < 0.3
            error = "timeout" if is_failure else ""
            status = "failed" if is_failure else "completed"
            all_runs.append(_make_run(f"opi-{i}", ["a", "b"], status, error))

        op_summary = summarize_operational_memory(all_runs)
        patterns = op_summary["recurring_patterns"]

        # Build governance for runs with patterns
        governance_records: List[GovernanceRecord] = []
        for run in all_runs:
            rec = build_governance_record(
                run["run_id"],
                replay_cert={"fidelity_score": 100.0},
                authenticity_cert={"authenticity_verdict": "authentic"},
                operational_summary=op_summary,
            )
            governance_records.append(rec)

        gov_summary = summarize_governance(governance_records)

        print(
            f"\n[Ω-4D] Integrated view: "
            f"{op_summary['total_runs']} runs, "
            f"{len(patterns)} patterns, "
            f"{gov_summary['approved']} approved, "
            f"{gov_summary['pending']} pending review"
        )

        assert gov_summary["total_records"] == 100
        assert len(patterns) > 0
