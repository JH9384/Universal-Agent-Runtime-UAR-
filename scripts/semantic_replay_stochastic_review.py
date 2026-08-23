#!/usr/bin/env python3
"""Stratified stochastic review for Ω-7B.S Semantic Replay.

This validation harness exercises distinct semantic mutation families and
semantic-null controls. It is observational/test code only.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from dataclasses import replace

from uar.core.semantic_trace import (
    CandidateDecision,
    ComparisonOutcome,
    DecisionState,
    SemanticStage,
    SemanticTrace,
    compare_semantic_traces,
)


FAMILIES = ("G", "A", "E", "K", "P", "O", "NULL")


def baseline_trace() -> SemanticTrace:
    return SemanticTrace(
        stages=(
            SemanticStage(
                stage_id="s0",
                generated=frozenset({"A", "B", "C"}),
                decisions=(
                    CandidateDecision("A", DecisionState.ADMIT, evidence_refs=("eA",)),
                    CandidateDecision("B", DecisionState.ADMIT, evidence_refs=("eB",)),
                    CandidateDecision("C", DecisionState.REJECT, constraint_id="policy-C"),
                ),
                dependencies=(),
            ),
            SemanticStage(
                stage_id="s1",
                generated=frozenset({"A", "B"}),
                decisions=(
                    CandidateDecision("A", DecisionState.ADMIT, evidence_refs=("eA",)),
                    CandidateDecision("B", DecisionState.REJECT, constraint_id="policy-B"),
                ),
                committed="A",
                dependencies=("s0",),
                terminal=True,
            ),
        ),
        final_result="A",
    )


def mutate(trace: SemanticTrace, family: str, rng: random.Random) -> SemanticTrace:
    stages = list(trace.stages)
    if family == "G":
        s = stages[0]
        phantom = f"phantom-{rng.randrange(1_000_000)}"
        stages[0] = replace(
            s,
            generated=frozenset(set(s.generated) | {phantom}),
            decisions=s.decisions + (CandidateDecision(phantom, DecisionState.REJECT),),
        )
    elif family == "A":
        s = stages[0]
        decisions = list(s.decisions)
        decisions[1] = replace(decisions[1], state=DecisionState.DEFER)
        stages[0] = replace(s, decisions=tuple(decisions))
    elif family == "E":
        s = stages[0]
        decisions = list(s.decisions)
        decisions[0] = replace(decisions[0], evidence_refs=("eA-mutated",))
        stages[0] = replace(s, decisions=tuple(decisions))
    elif family == "K":
        s = stages[1]
        decisions = tuple(
            replace(d, state=DecisionState.ADMIT)
            if d.candidate_id == "B"
            else d
            for d in s.decisions
        )
        stages[1] = replace(s, decisions=decisions, committed="B")
        return SemanticTrace(stages=tuple(stages), final_result="B")
    elif family == "P":
        s = stages[1]
        stages[1] = replace(s, dependencies=())
    elif family == "O":
        s = stages[0]
        decisions = tuple(d for d in s.decisions if d.candidate_id != "B")
        stages[0] = replace(s, decisions=decisions)
    elif family == "NULL":
        stages = list(reversed(stages))
    else:
        raise ValueError(f"unknown family: {family}")
    return SemanticTrace(stages=tuple(stages), final_result=trace.final_result)


def run(iterations: int, seed: int) -> dict:
    rng = random.Random(seed)
    counts = Counter()
    failures = Counter()

    for index in range(iterations):
        family = FAMILIES[index % len(FAMILIES)]
        base = baseline_trace()
        candidate = mutate(base, family, rng)
        report = compare_semantic_traces(base, candidate)
        counts[family] += 1

        if family == "NULL":
            if report.outcome is not ComparisonOutcome.EQUIVALENT:
                failures[family] += 1
        elif family == "O":
            if report.outcome is not ComparisonOutcome.INDETERMINATE:
                failures[family] += 1
        else:
            if report.outcome is not ComparisonOutcome.DIFFERENT:
                failures[family] += 1

    return {
        "iterations": iterations,
        "seed": seed,
        "counts": dict(counts),
        "failures": dict(failures),
        "all_passed": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=14_000)
    parser.add_argument("--seed", type=int, default=2049)
    args = parser.parse_args()
    result = run(args.iterations, args.seed)
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
