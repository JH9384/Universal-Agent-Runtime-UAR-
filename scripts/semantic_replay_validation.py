#!/usr/bin/env python3
"""Run the Ω-7B.S semantic replay mutation campaign.

This is a validation harness, not a production execution component. It seeds
synthetic result-equivalent mutations and checks that semantic comparison finds
their first causal divergence while remaining invariant to harmless stage
reordering by stable stage id.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import replace

from uar.core.semantic_trace import (
    CandidateDecision,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
)


def make_baseline(rng: random.Random, stage_count: int = 5) -> SemanticTrace:
    candidates = [f"c{i}" for i in range(6)]
    stages = []
    admitted = set(candidates)
    for index in range(stage_count):
        stage_id = f"s{index}"
        decisions = []
        for candidate in candidates:
            if candidate not in admitted:
                continue
            state = DecisionState.ADMIT
            if len(admitted) > 1 and rng.random() < 0.22:
                state = DecisionState.REJECT
                admitted.remove(candidate)
            decisions.append(CandidateDecision(candidate, state))
        if not admitted:
            winner = rng.choice(candidates)
            admitted.add(winner)
            decisions.append(CandidateDecision(winner, DecisionState.ADMIT))
        stages.append(
            SemanticStage(
                stage_id=stage_id,
                generated=frozenset(d.candidate_id for d in decisions),
                decisions=tuple(sorted(decisions, key=lambda d: d.candidate_id)),
                committed=(
                    sorted(admitted)[0] if index == stage_count - 1 else None
                ),
                dependencies=((f"s{index - 1}",) if index else ()),
            )
        )
    result = sorted(admitted)[0]
    final_stage = stages[-1]
    stages[-1] = replace(final_stage, committed=result)
    return SemanticTrace(stages=tuple(stages), final_result=result)


def mutate_same_result(trace: SemanticTrace, rng: random.Random) -> SemanticTrace:
    """Seed a semantic mutation while preserving final_result."""

    stages = list(trace.stages)
    candidate_indices = [i for i, stage in enumerate(stages) if stage.decisions]
    index = rng.choice(candidate_indices)
    stage = stages[index]
    decisions = list(stage.decisions)

    mutable = [
        i
        for i, decision in enumerate(decisions)
        if decision.candidate_id != trace.final_result
    ]
    if not mutable:
        # Generation-only mutation: add a rejected candidate that never wins.
        phantom = f"phantom-{rng.randrange(1_000_000)}"
        decisions.append(CandidateDecision(phantom, DecisionState.REJECT))
        stages[index] = replace(
            stage,
            generated=frozenset(set(stage.generated) | {phantom}),
            decisions=tuple(sorted(decisions, key=lambda d: d.candidate_id)),
        )
        return SemanticTrace(stages=tuple(stages), final_result=trace.final_result)

    decision_index = rng.choice(mutable)
    original = decisions[decision_index]
    new_state = {
        DecisionState.ADMIT: DecisionState.REJECT,
        DecisionState.REJECT: DecisionState.DEFER,
        DecisionState.DEFER: DecisionState.CONFLICT,
        DecisionState.CONFLICT: DecisionState.REJECT,
    }[original.state]
    decisions[decision_index] = replace(
        original,
        state=new_state,
        reason_code="seeded-semantic-mutation",
    )
    stages[index] = replace(
        stage,
        decisions=tuple(sorted(decisions, key=lambda d: d.candidate_id)),
    )
    return SemanticTrace(stages=tuple(stages), final_result=trace.final_result)


def harmless_reorder(trace: SemanticTrace, rng: random.Random) -> SemanticTrace:
    stages = list(trace.stages)
    rng.shuffle(stages)
    return SemanticTrace(stages=tuple(stages), final_result=trace.final_result)


def run_campaign(iterations: int, seed: int) -> dict:
    rng = random.Random(seed)
    detected = 0
    localized = 0
    false_positives = 0

    for _ in range(iterations):
        baseline = make_baseline(rng)
        mutated = mutate_same_result(baseline, rng)
        report = compare_semantic_traces(baseline, mutated)
        if report.result_equivalent and not report.filtration_equivalent:
            detected += 1
        if report.first_divergence.category in {"G-", "A-", "E-", "K-"}:
            localized += 1

        reordered = harmless_reorder(baseline, rng)
        reorder_report = compare_semantic_traces(baseline, reordered)
        if not reorder_report.filtration_equivalent:
            false_positives += 1

    return {
        "iterations": iterations,
        "seed": seed,
        "result_equivalent_mutations_detected": detected,
        "first_divergences_localized": localized,
        "harmless_reorder_false_positives": false_positives,
        "detection_rate": detected / iterations if iterations else 1.0,
        "localization_rate": localized / iterations if iterations else 1.0,
        "false_positive_rate": false_positives / iterations if iterations else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=2049)
    args = parser.parse_args()

    result = run_campaign(args.iterations, args.seed)
    for key, value in result.items():
        print(f"{key}: {value}")

    passed = (
        result["detection_rate"] == 1.0
        and result["localization_rate"] == 1.0
        and result["false_positive_rate"] == 0.0
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
