from uar.core.semantic_trace import (
    CandidateDecision,
    ComparisonOutcome,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
    project_nonsemantic_events,
    semantic_trace_from_events,
    semantic_trace_hash,
    validate_semantic_trace,
    verify_decision_certificates,
)


def test_four_state_duality_is_explicit():
    assert DecisionState.ADMIT.dual is DecisionState.REJECT
    assert DecisionState.REJECT.dual is DecisionState.ADMIT
    assert DecisionState.DEFER.dual is DecisionState.DEFER
    assert DecisionState.CONFLICT.dual is DecisionState.CONFLICT
    assert DecisionState.ADMIT.support_obstruction == (1, 0)
    assert DecisionState.REJECT.support_obstruction == (0, 1)


def test_unobserved_is_not_defer_and_yields_indeterminate():
    complete = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A"}),
                decisions=(CandidateDecision("A", DecisionState.DEFER),),
                terminal=True,
            ),
        )
    )
    missing = SemanticTrace(
        stages=(SemanticStage("s", frozenset({"A"}), terminal=True),)
    )

    report = compare_semantic_traces(complete, missing)

    assert complete.stages[0].unobserved() == frozenset()
    assert missing.stages[0].unobserved() == frozenset({"A"})
    assert report.first_divergence.category == "O-"
    assert report.outcome is ComparisonOutcome.INDETERMINATE


def test_observation_gap_cannot_hide_observed_downstream_difference():
    left = SemanticTrace(
        stages=(
            SemanticStage("s1", frozenset({"x"})),
            SemanticStage(
                "s2",
                frozenset({"y"}),
                decisions=(CandidateDecision("y", DecisionState.ADMIT),),
                dependencies=("s1",),
            ),
        ),
        final_result="same",
    )
    right = SemanticTrace(
        stages=(
            SemanticStage(
                "s1",
                frozenset({"x"}),
                decisions=(CandidateDecision("x", DecisionState.ADMIT),),
            ),
            SemanticStage(
                "s2",
                frozenset({"y"}),
                decisions=(
                    CandidateDecision(
                        "y",
                        DecisionState.REJECT,
                        reason_code="blocked",
                    ),
                ),
                dependencies=("s1",),
            ),
        ),
        final_result="same",
    )

    report = compare_semantic_traces(left, right)

    assert report.minimal_divergences[0].category == "O-"
    assert report.outcome is ComparisonOutcome.DIFFERENT


def test_reason_change_cannot_be_zero_distance_and_divergent():
    left = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A"}),
                decisions=(
                    CandidateDecision(
                        "A", DecisionState.ADMIT, reason_code="r1"
                    ),
                ),
                terminal=True,
            ),
        )
    )
    right = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A"}),
                decisions=(
                    CandidateDecision(
                        "A", DecisionState.ADMIT, reason_code="r2"
                    ),
                ),
                terminal=True,
            ),
        )
    )

    report = compare_semantic_traces(left, right)

    assert report.first_divergence.category == "A-"
    assert report.distance.identical is False
    assert report.distance.filtration > 0.0
    assert report.outcome is ComparisonOutcome.DIFFERENT


def test_evidence_attachment_is_relational_not_global_inventory():
    left = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A", "B"}),
                decisions=(
                    CandidateDecision(
                        "A", DecisionState.ADMIT, evidence_refs=("e1",)
                    ),
                    CandidateDecision(
                        "B", DecisionState.ADMIT, evidence_refs=("e2",)
                    ),
                ),
                terminal=True,
            ),
        )
    )
    right = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A", "B"}),
                decisions=(
                    CandidateDecision(
                        "A", DecisionState.ADMIT, evidence_refs=("e2",)
                    ),
                    CandidateDecision(
                        "B", DecisionState.ADMIT, evidence_refs=("e1",)
                    ),
                ),
                terminal=True,
            ),
        )
    )

    report = compare_semantic_traces(left, right)

    assert left.stages[0].evidence_basis() == right.stages[0].evidence_basis()
    assert report.distance.evidence > 0.0
    assert report.first_divergence.category == "E-"


def test_dependency_mutation_is_semantic_even_when_stage_contents_match():
    s0 = SemanticStage(
        "s0",
        frozenset({"A"}),
        decisions=(CandidateDecision("A", DecisionState.ADMIT),),
    )
    left = SemanticTrace(
        stages=(
            s0,
            SemanticStage(
                "s1",
                frozenset({"A"}),
                decisions=(CandidateDecision("A", DecisionState.ADMIT),),
                dependencies=("s0",),
                terminal=True,
            ),
        )
    )
    right = SemanticTrace(
        stages=(
            s0,
            SemanticStage(
                "s1",
                frozenset({"A"}),
                decisions=(CandidateDecision("A", DecisionState.ADMIT),),
                dependencies=(),
                terminal=True,
            ),
        )
    )

    report = compare_semantic_traces(left, right)

    assert report.causal_equivalent is False
    assert report.distance.causal > 0.0
    assert report.first_divergence.category == "P-"
    assert report.outcome is ComparisonOutcome.DIFFERENT


def test_causal_finality_is_invariant_to_tuple_reordering():
    s0 = SemanticStage(
        "s0",
        frozenset({"A", "B"}),
        decisions=(
            CandidateDecision("A", DecisionState.ADMIT),
            CandidateDecision("B", DecisionState.ADMIT),
        ),
    )
    s1 = SemanticStage(
        "s1",
        frozenset({"A"}),
        decisions=(CandidateDecision("A", DecisionState.ADMIT),),
        dependencies=("s0",),
    )
    left = SemanticTrace(stages=(s0, s1), final_result="A")
    right = SemanticTrace(stages=(s1, s0), final_result="A")

    report = compare_semantic_traces(left, right)

    assert left.terminal_stage_ids() == frozenset({"s1"})
    assert right.terminal_stage_ids() == frozenset({"s1"})
    assert report.survivor_equivalent is True
    assert report.filtration_equivalent is True
    assert report.outcome is ComparisonOutcome.EQUIVALENT


def test_evidence_reconstruction_is_arrival_order_invariant():
    decision = {
        "type": "candidate_admitted",
        "payload": {"stage_id": "s", "candidate_id": "A"},
    }
    evidence = {
        "type": "evidence_acquired",
        "payload": {"stage_id": "s", "candidate_id": "A", "evidence_id": "e1"},
    }
    generated = {
        "type": "candidate_generated",
        "payload": {"stage_id": "s", "candidate_id": "A"},
    }

    before = semantic_trace_from_events((generated, evidence, decision))
    after = semantic_trace_from_events((generated, decision, evidence))

    assert semantic_trace_hash(before) == semantic_trace_hash(after)
    assert (
        compare_semantic_traces(before, after).outcome
        is ComparisonOutcome.EQUIVALENT
    )


def test_trace_validation_detects_conservation_and_causal_defects():
    trace = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A"}),
                decisions=(
                    CandidateDecision("A", DecisionState.ADMIT),
                    CandidateDecision("A", DecisionState.REJECT),
                    CandidateDecision("B", DecisionState.ADMIT),
                ),
                dependencies=("s", "missing"),
            ),
        )
    )

    codes = {issue.code for issue in validate_semantic_trace(trace)}

    assert "duplicate_candidate_decision" in codes
    assert "decision_without_generation" in codes
    assert "unknown_dependency" in codes
    assert "self_dependency" in codes
    assert "causal_cycle" in codes


def test_semantic_hash_ignores_stage_order_when_causal_structure_matches():
    s0 = SemanticStage("s0", frozenset(), dependencies=())
    s1 = SemanticStage("s1", frozenset(), dependencies=("s0",))
    left = SemanticTrace(stages=(s0, s1))
    right = SemanticTrace(stages=(s1, s0))

    assert semantic_trace_hash(left) == semantic_trace_hash(right)


def test_shadow_projection_removes_only_semantic_events():
    events = (
        {"type": "start", "payload": {}},
        {
            "type": "candidate_generated",
            "payload": {"stage_id": "s", "candidate_id": "A"},
        },
        {"type": "complete", "payload": {}},
    )

    projected = project_nonsemantic_events(events)

    assert [event["type"] for event in projected] == ["start", "complete"]


def test_certificate_integrity_is_separate_from_replay_equivalence():
    trace = SemanticTrace(
        stages=(
            SemanticStage(
                "s",
                frozenset({"A", "B"}),
                decisions=(
                    CandidateDecision(
                        "A", DecisionState.ADMIT, certificate_id="good"
                    ),
                    CandidateDecision(
                        "B", DecisionState.REJECT, certificate_id="bad"
                    ),
                ),
                terminal=True,
            ),
        )
    )

    report = verify_decision_certificates(trace, {"good": True, "bad": False})

    assert report.checked_certificates == 2
    assert report.verified is False
    assert report.invalid_certificates == (("s", "B", "bad"),)
