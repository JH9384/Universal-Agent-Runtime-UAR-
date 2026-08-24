from uar.core.semantic_trace import (
    CandidateDecision,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
    semantic_trace_from_events,
)


def _trace(*stages, final_result="A"):
    return SemanticTrace(stages=tuple(stages), final_result=final_result)


def test_same_result_can_hide_filtration_divergence():
    baseline = _trace(
        SemanticStage(
            stage_id="s1",
            generated=frozenset({"A", "B", "C", "D"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT),
                CandidateDecision("B", DecisionState.ADMIT),
                CandidateDecision("C", DecisionState.ADMIT),
                CandidateDecision("D", DecisionState.REJECT),
            ),
        ),
        SemanticStage(
            stage_id="s2",
            generated=frozenset({"A", "B", "C"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT),
                CandidateDecision("B", DecisionState.ADMIT),
                CandidateDecision("C", DecisionState.REJECT),
            ),
            committed="A",
        ),
    )
    candidate = _trace(
        SemanticStage(
            stage_id="s1",
            generated=frozenset({"A", "B", "C", "D"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT),
                CandidateDecision("B", DecisionState.REJECT),
                CandidateDecision("C", DecisionState.ADMIT),
                CandidateDecision("D", DecisionState.ADMIT),
            ),
        ),
        SemanticStage(
            stage_id="s2",
            generated=frozenset({"A", "C", "D"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT),
                CandidateDecision("C", DecisionState.REJECT),
                CandidateDecision("D", DecisionState.REJECT),
            ),
            committed="A",
        ),
    )

    report = compare_semantic_traces(baseline, candidate)

    assert report.result_equivalent is True
    assert report.filtration_equivalent is False
    assert report.distance.result == 0.0
    assert report.distance.filtration > 0.0
    assert report.first_divergence.stage_id == "s1"
    assert report.first_divergence.category == "A-"


def test_generation_divergence_is_classified_before_admissibility():
    baseline = _trace(
        SemanticStage("s1", frozenset({"A", "B"})),
    )
    candidate = _trace(
        SemanticStage("s1", frozenset({"A", "B", "C"})),
    )

    report = compare_semantic_traces(baseline, candidate)

    assert report.first_divergence.category == "G-"
    assert report.first_divergence.details["right_only"] == ["C"]


def test_evidence_divergence_is_detected_without_state_change():
    baseline = _trace(
        SemanticStage(
            "s1",
            frozenset({"A"}),
            decisions=(
                CandidateDecision(
                    "A",
                    DecisionState.ADMIT,
                    certificate_id="cert-1",
                    evidence_refs=("e1",),
                ),
            ),
            committed="A",
        ),
    )
    candidate = _trace(
        SemanticStage(
            "s1",
            frozenset({"A"}),
            decisions=(
                CandidateDecision(
                    "A",
                    DecisionState.ADMIT,
                    certificate_id="cert-2",
                    evidence_refs=("e2",),
                ),
            ),
            committed="A",
        ),
    )

    report = compare_semantic_traces(baseline, candidate)

    assert report.result_equivalent is True
    assert report.survivor_equivalent is True
    assert report.evidence_equivalent is False
    assert report.first_divergence.category == "E-"


def test_defer_is_not_equivalent_to_admit():
    baseline = _trace(
        SemanticStage(
            "s1",
            frozenset({"A"}),
            decisions=(CandidateDecision("A", DecisionState.DEFER),),
        )
    )
    candidate = _trace(
        SemanticStage(
            "s1",
            frozenset({"A"}),
            decisions=(CandidateDecision("A", DecisionState.ADMIT),),
        )
    )

    report = compare_semantic_traces(baseline, candidate)

    assert report.first_divergence.category == "A-"
    assert report.distance.filtration > 0.0


def test_stable_stage_ids_make_wall_clock_reordering_harmless():
    stage_a = SemanticStage(
        "a",
        frozenset({"A"}),
        decisions=(CandidateDecision("A", DecisionState.ADMIT),),
    )
    stage_b = SemanticStage(
        "b",
        frozenset({"B"}),
        decisions=(CandidateDecision("B", DecisionState.ADMIT),),
    )

    left = SemanticTrace(stages=(stage_a, stage_b), final_result="B")
    right = SemanticTrace(stages=(stage_b, stage_a), final_result="B")

    report = compare_semantic_traces(left, right)

    assert report.filtration_equivalent is True
    assert report.first_divergence.category is None


def test_semantic_trace_reconstructs_from_shadow_events():
    events = [
        {
            "type": "semantic_stage",
            "payload": {"stage_id": "s1", "dependencies": []},
        },
        {
            "type": "candidate_generated",
            "payload": {"stage_id": "s1", "candidate_id": "A"},
        },
        {
            "type": "candidate_admitted",
            "payload": {
                "stage_id": "s1",
                "candidate_id": "A",
                "constraint_id": "policy-1",
                "certificate_id": "cert-1",
                "evidence_refs": ["e1"],
            },
        },
        {
            "type": "evidence_acquired",
            "payload": {
                "stage_id": "s1",
                "candidate_id": "A",
                "evidence_id": "e2",
            },
        },
        {
            "type": "candidate_committed",
            "payload": {"stage_id": "s1", "candidate_id": "A"},
        },
        {
            "type": "complete",
            "payload": {"semantic_result": "A"},
        },
    ]

    trace = semantic_trace_from_events(events)

    assert trace.final_result == "A"
    assert len(trace.stages) == 1
    stage = trace.stages[0]
    assert stage.stage_id == "s1"
    assert stage.committed == "A"
    assert stage.partition()[DecisionState.ADMIT] == frozenset({"A"})
    assert stage.evidence_basis() == frozenset(
        {"e1", "e2", "certificate:cert-1"}
    )


def test_identical_traces_have_zero_vector_distance():
    trace = _trace(
        SemanticStage(
            "s1",
            frozenset({"A"}),
            decisions=(CandidateDecision("A", DecisionState.ADMIT),),
            committed="A",
        )
    )

    report = compare_semantic_traces(trace, trace)

    assert report.distance.identical is True
    assert report.first_divergence.category is None
