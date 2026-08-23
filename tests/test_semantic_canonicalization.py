from uar.core.semantic_trace import (
    CandidateDecision,
    ComparisonOutcome,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
    projected_event_hash,
    remap_semantic_trace,
    semantic_trace_hash,
)


def _admit(stage_id: str, candidate: str, dependencies=()):
    return SemanticStage(
        stage_id=stage_id,
        generated=frozenset({candidate}),
        decisions=(CandidateDecision(candidate, DecisionState.ADMIT),),
        dependencies=tuple(dependencies),
    )


def test_redundant_dependency_edge_is_canonically_equivalent():
    # a -> b -> c implies a -> c. Adding the redundant a -> c raw edge should
    # not change causal reachability semantics.
    a = _admit("a", "A")
    b = _admit("b", "A", ("a",))
    c_minimal = _admit("c", "A", ("b",))
    c_redundant = _admit("c", "A", ("a", "b"))

    left = SemanticTrace(stages=(a, b, c_minimal), final_result="A")
    right = SemanticTrace(stages=(a, b, c_redundant), final_result="A")

    report = compare_semantic_traces(left, right)

    assert report.causal_equivalent is True
    assert report.outcome is ComparisonOutcome.EQUIVALENT
    assert semantic_trace_hash(left) == semantic_trace_hash(right)


def test_declared_identifier_isomorphism_can_normalize_coordinate_changes():
    left = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A"}),
                decisions=(
                    CandidateDecision("A", DecisionState.ADMIT, evidence_refs=("e1",)),
                ),
                committed="A",
                terminal=True,
            ),
        ),
        final_result="A",
    )
    renamed = SemanticTrace(
        stages=(
            SemanticStage(
                "x",
                frozenset({"Z"}),
                decisions=(
                    CandidateDecision("Z", DecisionState.ADMIT, evidence_refs=("q1",)),
                ),
                committed="Z",
                terminal=True,
            ),
        ),
        final_result="Z",
    )

    normalized = remap_semantic_trace(
        renamed,
        stage_ids={"x": "s"},
        candidate_ids={"Z": "A"},
        evidence_ids={"q1": "e1"},
    )

    assert compare_semantic_traces(left, normalized).outcome is ComparisonOutcome.EQUIVALENT
    assert semantic_trace_hash(left) == semantic_trace_hash(normalized)


def test_projected_event_hash_ignores_shadow_semantic_events():
    baseline = (
        {"type": "start", "payload": {"run": "1"}},
        {"type": "complete", "payload": {"result_id": "A"}},
    )
    shadow = (
        {"type": "start", "payload": {"run": "1"}},
        {"type": "candidate_generated", "payload": {"stage_id": "s", "candidate_id": "A"}},
        {"type": "candidate_admitted", "payload": {"stage_id": "s", "candidate_id": "A"}},
        {"type": "complete", "payload": {"result_id": "A"}},
    )

    assert projected_event_hash(baseline) == projected_event_hash(shadow)
