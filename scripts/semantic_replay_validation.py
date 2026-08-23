#!/usr/bin/env python3
"""Run the Ω-7B.S stratified semantic replay validation campaign.

The campaign separates semantic-changing mutations from semantic-null controls
and reports results by family. Seed 2049 is a reproducibility seed only.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter, defaultdict
from dataclasses import replace

from uar.core.semantic_trace import (
    CandidateDecision,
    ComparisonOutcome,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
)


MUTATION_FAMILIES = ("G", "A", "E", "K", "P", "O", "NULL")
EXPECTED_CATEGORY = {
    "G": "G-",
    "A": "A-",
    "E": "E-",
    "K": "K-",
    "P": "P-",
    "O": "O-",
    "NULL": None,
}
EXPECTED_OUTCOME = {
    "G": ComparisonOutcome.DIFFERENT,
    "A": ComparisonOutcome.DIFFERENT,
    "E": ComparisonOutcome.DIFFERENT,
    "K": ComparisonOutcome.DIFFERENT,
    "P": ComparisonOutcome.DIFFERENT,
    "O": ComparisonOutcome.INDETERMINATE,
    "NULL": ComparisonOutcome.EQUIVALENT,
}


def make_baseline(rng: random.Random) -> SemanticTrace:
    """Create a fully observed causal trace with all four decision states present."""

    suffix = rng.randrange(1_000_000)
    evidence_a = f"eA-{suffix}"
    stages = (
        SemanticStage(
            stage_id="s0",
            generated=frozenset({"A", "B", "C", "D", "E", "F"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT, evidence_refs=(evidence_a,)),
                CandidateDecision("B", DecisionState.ADMIT, evidence_refs=("eB",)),
                CandidateDecision("C", DecisionState.ADMIT),
                CandidateDecision("D", DecisionState.REJECT, constraint_id="policy-D"),
                CandidateDecision("E", DecisionState.DEFER),
                CandidateDecision("F", DecisionState.CONFLICT, constraint_id="policy-F"),
            ),
            dependencies=(),
        ),
        SemanticStage(
            stage_id="s1",
            generated=frozenset({"A", "B", "C"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT, evidence_refs=(evidence_a,)),
                CandidateDecision("B", DecisionState.REJECT, constraint_id="policy-B"),
                CandidateDecision("C", DecisionState.ADMIT),
            ),
            dependencies=("s0",),
        ),
        SemanticStage(
            stage_id="s2",
            generated=frozenset({"A", "C"}),
            decisions=(
                CandidateDecision("A", DecisionState.ADMIT, evidence_refs=(evidence_a,)),
                CandidateDecision("C", DecisionState.REJECT, constraint_id="policy-C"),
            ),
            dependencies=("s1",),
        ),
        SemanticStage(
            stage_id="s3",
            generated=frozenset({"A"}),
            decisions=(CandidateDecision("A", DecisionState.ADMIT),),
            dependencies=("s2",),
        ),
        SemanticStage(
            stage_id="s4",
            generated=frozenset({"A"}),
            decisions=(CandidateDecision("A", DecisionState.ADMIT),),
            committed="A",
            dependencies=("s3",),
            terminal=True,
        ),
    )
    return SemanticTrace(stages=stages, final_result="A")


def mutate(trace: SemanticTrace, family: str, rng: random.Random) -> SemanticTrace:
    stages = list(trace.stages)

    if family == "G":
        index = rng.choice((1, 2, 3))
        stage = stages[index]
        phantom = f"phantom-{rng.randrange(1_000_000)}"
        stages[index] = replace(
            stage,
            generated=frozenset(set(stage.generated) | {phantom}),
            decisions=stage.decisions + (
                CandidateDecision(phantom, DecisionState.REJECT, reason_code="seeded-G"),
            ),
        )

    elif family == "A":
        stage = stages[1]
        decisions = list(stage.decisions)
        target = next(i for i, d in enumerate(decisions) if d.candidate_id == "B")
        decisions[target] = replace(
            decisions[target], state=DecisionState.DEFER, reason_code="seeded-A"
        )
        stages[1] = replace(stage, decisions=tuple(decisions))

    elif family == "E":
        index = rng.choice((0, 1, 2))
        stage = stages[index]
        decisions = list(stage.decisions)
        target = next(i for i, d in enumerate(decisions) if d.candidate_id == "A")
        decisions[target] = replace(
            decisions[target], evidence_refs=(f"mutated-evidence-{rng.randrange(1_000_000)}",)
        )
        stages[index] = replace(stage, decisions=tuple(decisions))

    elif family == "K":
        # Result-equivalent commitment mutation: introduce an intermediate commit
        # while preserving the final committed result A.
        stage = stages[0]
        stages[0] = replace(stage, committed="B")

    elif family == "P":
        # Change causal structure without changing stage contents or final result.
        stage = stages[3]
        stages[3] = replace(stage, dependencies=("s1",))

    elif family == "O":
        # Observation-loss mutation: execution candidates are unchanged but one
        # decision observation is absent. Correct verdict is INDETERMINATE.
        stage = stages[2]
        stages[2] = replace(
            stage,
            decisions=tuple(d for d in stage.decisions if d.candidate_id != "A"),
        )

    elif family == "NULL":
        # Pure representation change: tuple order changes, causal structure does not.
        rng.shuffle(stages)

    else:
        raise ValueError(f"unknown mutation family: {family}")

    return SemanticTrace(stages=tuple(stages), final_result=trace.final_result)


def run_campaign(iterations: int, seed: int) -> dict:
    rng = random.Random(seed)
    counts = Counter()
    detected = Counter()
    localized = Counter()
    outcome_errors = Counter()
    result_regressions = Counter()
    distance_sums = defaultdict(float)

    for iteration in range(iterations):
        family = MUTATION_FAMILIES[iteration % len(MUTATION_FAMILIES)]
        baseline = make_baseline(rng)
        candidate = mutate(baseline, family, rng)
        report = compare_semantic_traces(baseline, candidate)

        counts[family] += 1
        distance_sums[family] += report.distance.filtration

        expected_outcome = EXPECTED_OUTCOME[family]
        expected_category = EXPECTED_CATEGORY[family]

        if report.outcome is expected_outcome:
            detected[family] += 1
        else:
            outcome_errors[family] += 1

        if expected_category is None:
            if report.first_divergence.category is None:
                localized[family] += 1
        elif report.first_divergence.category == expected_category:
            localized[family] += 1

        # Every semantic-changing family except observation loss and NULL is
        # intentionally result-equivalent at the final output level.
        if family in {"G", "A", "E", "K", "P"} and not report.result_equivalent:
            result_regressions[family] += 1

    by_family = {}
    for family in MUTATION_FAMILIES:
        n = counts[family]
        by_family[family] = {
            "count": n,
            "expected_outcome": EXPECTED_OUTCOME[family].value,
            "expected_category": EXPECTED_CATEGORY[family],
            "outcome_accuracy": detected[family] / n if n else 1.0,
            "localization_accuracy": localized[family] / n if n else 1.0,
            "result_equivalence_regressions": result_regressions[family],
            "mean_filtration_distance": distance_sums[family] / n if n else 0.0,
        }

    passed = (
        not outcome_errors
        and not result_regressions
        and all(
            by_family[family]["localization_accuracy"] == 1.0
            for family in MUTATION_FAMILIES
        )
    )

    return {
        "iterations": iterations,
        "seed": seed,
        "by_family": by_family,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=14_000)
    parser.add_argument("--seed", type=int, default=2049)
    args = parser.parse_args()

    result = run_campaign(args.iterations, args.seed)
    print(f"iterations: {result['iterations']}")
    print(f"seed: {result['seed']}")
    for family, stats in result["by_family"].items():
        print(f"{family}: {stats}")
    print(f"passed: {result['passed']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
