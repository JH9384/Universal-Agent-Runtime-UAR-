import pytest

from scripts.semantic_concurrent_shadow_review import (
    MIN_CONFIRMATORY_SAMPLES_PER_STRATUM,
    build_report,
)


def test_concurrent_shadow_pilot_smoke_has_no_semantic_drift():
    report = build_report(
        mode="pilot",
        samples_per_stratum=2,
        seed=6143,
        concurrency_levels=(1,),
    )

    assert report["passed"] is True
    assert report["gate_enforced"] is False
    assert {stratum["workload"] for stratum in report["strata"]} == {
        "greedy_wide",
        "dag_diamond",
    }
    for stratum in report["strata"]:
        assert stratum["projection_mismatches"] == 0
        assert stratum["result_mismatches"] == 0
        assert stratum["integrity_issues"] == 0
        assert stratum["semantic_distribution"]["js_divergence_bits"] == 0
        assert stratum["semantic_distribution"]["total_variation"] == 0


def test_confirmatory_mode_rejects_underpowered_sample_count():
    with pytest.raises(ValueError, match="confirmatory mode requires"):
        build_report(
            mode="confirmatory",
            samples_per_stratum=MIN_CONFIRMATORY_SAMPLES_PER_STRATUM - 1,
            seed=8191,
            concurrency_levels=(1,),
        )
