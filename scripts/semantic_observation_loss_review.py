#!/usr/bin/env python3
"""Inject telemetry loss into identical latent semantic executions.

The experiment checks that observation loss produces INDETERMINATE rather than
false semantic DIFFERENT judgments. Seed 2049 is reproducibility-only.
"""

from __future__ import annotations

import argparse
import random
from collections import Counter

from uar.core.semantic_trace import (
    ComparisonOutcome,
    compare_semantic_traces,
    semantic_trace_from_events,
)


def make_latent_events(stage_count: int = 5, candidates_per_stage: int = 4):
    events = []
    for stage_index in range(stage_count):
        stage_id = f"s{stage_index}"
        dependencies = [f"s{stage_index - 1}"] if stage_index else []
        events.append(
            {
                "type": "semantic_stage",
                "payload": {
                    "stage_id": stage_id,
                    "dependencies": dependencies,
                    "terminal": stage_index == stage_count - 1,
                },
            }
        )
        for candidate_index in range(candidates_per_stage):
            candidate_id = f"c{candidate_index}"
            events.append(
                {
                    "type": "candidate_generated",
                    "payload": {
                        "stage_id": stage_id,
                        "candidate_id": candidate_id,
                    },
                }
            )
            event_type = (
                "candidate_admitted"
                if candidate_index == 0
                else "candidate_rejected"
            )
            events.append(
                {
                    "type": event_type,
                    "payload": {
                        "stage_id": stage_id,
                        "candidate_id": candidate_id,
                        "reason_code": "latent-fixed-policy",
                    },
                }
            )
    events.append(
        {
            "type": "candidate_committed",
            "payload": {
                "stage_id": f"s{stage_count - 1}",
                "candidate_id": "c0",
            },
        }
    )
    events.append(
        {
            "type": "complete",
            "payload": {"semantic_result": "c0"},
        }
    )
    return tuple(events)


def observe(events, loss_probability: float, rng: random.Random):
    decision_types = {
        "candidate_admitted",
        "candidate_rejected",
        "candidate_deferred",
        "candidate_conflicted",
    }
    out = []
    for event in events:
        if event.get("type") in decision_types and rng.random() < loss_probability:
            continue
        out.append(event)
    return tuple(out)


def run(iterations: int, seed: int, probabilities):
    rng = random.Random(seed)
    latent = make_latent_events()
    results = {}

    for probability in probabilities:
        counts = Counter()
        for _ in range(iterations):
            left = semantic_trace_from_events(observe(latent, probability, rng))
            right = semantic_trace_from_events(observe(latent, probability, rng))
            report = compare_semantic_traces(left, right)
            counts[report.outcome.value] += 1
        results[probability] = {
            "counts": dict(counts),
            "different_rate": counts[ComparisonOutcome.DIFFERENT.value] / iterations,
            "indeterminate_rate": counts[ComparisonOutcome.INDETERMINATE.value]
            / iterations,
            "equivalent_rate": counts[ComparisonOutcome.EQUIVALENT.value]
            / iterations,
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=2049)
    parser.add_argument(
        "--loss",
        type=float,
        nargs="*",
        default=(0.0, 0.001, 0.005, 0.01, 0.02, 0.05),
    )
    args = parser.parse_args()

    results = run(args.iterations, args.seed, args.loss)
    print(f"seed: {args.seed}")
    print(f"iterations_per_probability: {args.iterations}")
    for probability, result in results.items():
        print(f"loss={probability}: {result}")

    # Latent traces are identical. Observation loss may make the comparison
    # indeterminate, but must never create a false semantic-difference verdict.
    passed = all(result["different_rate"] == 0.0 for result in results.values())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
