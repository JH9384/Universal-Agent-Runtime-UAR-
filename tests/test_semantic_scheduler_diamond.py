from uar.core.semantic_trace import (
    CandidateDecision,
    ComparisonOutcome,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    local_diamond_report,
)


def _stage(stage_id: str, candidate: str, state: DecisionState, reason: str | None = None):
    return SemanticStage(
        stage_id=stage_id,
        generated=frozenset({candidate}),
        decisions=(CandidateDecision(candidate, state, reason_code=reason),),
    )


def test_flat_independent_diamond_is_invariant_to_linearization_order():
    a = _stage("a", "A", DecisionState.ADMIT)
    b = _stage("b", "B", DecisionState.ADMIT)
    left = SemanticTrace(stages=(a, b), final_result="ok")
    right = SemanticTrace(stages=(b, a), final_result="ok")

    report = local_diamond_report(left, right)

    assert report.outcome is ComparisonOutcome.EQUIVALENT
    assert report.distance.identical is True


def test_nonflat_diamond_detects_declared_independence_that_changes_semantics():
    a = _stage("a", "A", DecisionState.ADMIT)
    b_left = _stage("b", "B", DecisionState.ADMIT, reason="after-a")
    b_right = _stage("b", "B", DecisionState.REJECT, reason="before-a")
    left = SemanticTrace(stages=(a, b_left), final_result="ok")
    right = SemanticTrace(stages=(b_right, a), final_result="ok")

    report = local_diamond_report(left, right)

    assert report.result_equivalent is True
    assert report.outcome is ComparisonOutcome.DIFFERENT
    assert report.first_divergence.category == "A-"
    assert report.distance.max_filtration > 0.0


def test_independent_earliest_divergences_form_a_minimal_antichain():
    left = SemanticTrace(
        stages=(
            _stage("a", "A", DecisionState.ADMIT),
            _stage("b", "B", DecisionState.ADMIT),
        )
    )
    right = SemanticTrace(
        stages=(
            _stage("a", "A", DecisionState.REJECT),
            _stage("b", "B", DecisionState.REJECT),
        )
    )

    report = local_diamond_report(left, right)

    assert {d.stage_id for d in report.minimal_divergences} == {"a", "b"}
    assert all(d.category == "A-" for d in report.minimal_divergences)
