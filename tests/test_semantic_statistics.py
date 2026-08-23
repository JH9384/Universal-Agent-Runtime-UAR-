from uar.core.semantic_statistics import (
    compare_semantic_distributions,
    empirical_distribution,
    entropy_bits,
    jensen_shannon_divergence_bits,
    total_variation_distance,
    version_information_bits,
)
from uar.core.semantic_trace import CandidateDecision, DecisionState, SemanticStage, SemanticTrace


def _trace(label: str, result: str = "A") -> SemanticTrace:
    return SemanticTrace(
        stages=(
            SemanticStage(
                stage_id="s",
                generated=frozenset({"A"}),
                decisions=(
                    CandidateDecision(
                        "A",
                        DecisionState.ADMIT,
                        reason_code=label,
                    ),
                ),
                committed="A",
                terminal=True,
            ),
        ),
        final_result=result,
    )


def test_distribution_primitives_are_zero_for_identical_laws():
    p = empirical_distribution(("a", "a", "b"))
    assert jensen_shannon_divergence_bits(p, p) == 0.0
    assert total_variation_distance(p, p) == 0.0
    assert entropy_bits({"a": 1.0}) == 0.0


def test_same_output_can_have_nonzero_process_distribution_drift():
    t1 = _trace("mode-1")
    t2 = _trace("mode-2")
    baseline = [t1] * 9 + [t2]
    candidate = [t1] * 5 + [t2] * 5

    report = compare_semantic_distributions(baseline, candidate)

    assert all(trace.final_result == "A" for trace in baseline + candidate)
    assert report.js_divergence_bits > 0.0
    assert report.total_variation > 0.0
    assert version_information_bits(baseline, candidate) == report.js_divergence_bits


def test_shadow_latency_delta_is_reported_separately_from_semantic_drift():
    trace = _trace("stable")
    report = compare_semantic_distributions(
        [trace] * 4,
        [trace] * 4,
        baseline_latencies=(1.0, 1.0, 1.0, 1.0),
        candidate_latencies=(1.1, 1.1, 1.1, 1.1),
    )

    assert report.distribution_equivalent is True
    assert abs(report.mean_latency_delta - 0.1) < 1e-12
    assert abs(report.p95_latency_delta - 0.1) < 1e-12
