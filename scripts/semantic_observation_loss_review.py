#!/usr/bin/env python3
"""Inject telemetry loss into identical and divergent latent executions.

The experiment checks both sides of the observation contract:

* identical latent executions never become falsely DIFFERENT; and
* divergent latent executions never become falsely EQUIVALENT.

When telemetry erases the evidence needed to discriminate two divergent latent
executions, the correct result is INDETERMINATE. Seed 2049 is
reproducibility-only.
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


def make_latent_events(
    stage_count: int = 5,
    candidates_per_stage: int = 4,
    *,
    divergent_reason: bool = False,
):
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
                        "reason_code": (
                            "latent-divergent-policy"
                            if divergent_reason
                            and stage_index == stage_count - 1
                            and candidate_index == 0
                            else "latent-fixed-policy"
                        ),
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
    divergent_latent = make_latent_events(divergent_reason=True)
    results = {}

    for probability in probabilities:
        identical_counts = Counter()
        divergent_counts = Counter()
        for _ in range(iterations):
            left = semantic_trace_from_events(observe(latent, probability, rng))
            right = semantic_trace_from_events(observe(latent, probability, rng))
            report = compare_semantic_traces(left, right)
            identical_counts[report.outcome.value] += 1

            divergent_left = semantic_trace_from_events(
                observe(latent, probability, rng)
            )
            divergent_right = semantic_trace_from_events(
                observe(divergent_latent, probability, rng)
            )
            divergent_report = compare_semantic_traces(
                divergent_left, divergent_right
            )
            divergent_counts[divergent_report.outcome.value] += 1

        results[probability] = {
            "identical": {
                "counts": dict(identical_counts),
                "false_different_rate": identical_counts[
                    ComparisonOutcome.DIFFERENT.value
                ]
                / iterations,
                "indeterminate_rate": identical_counts[
                    ComparisonOutcome.INDETERMINATE.value
                ]
                / iterations,
            },
            "divergent": {
                "counts": dict(divergent_counts),
                "false_equivalent_rate": divergent_counts[
                    ComparisonOutcome.EQUIVALENT.value
                ]
                / iterations,
                "indeterminate_rate": divergent_counts[
                    ComparisonOutcome.INDETERMINATE.value
                ]
                / iterations,
            },
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

    # Observation loss may make either comparison indeterminate. It must never
    # invent a difference for identical latent traces or erase a known latent
    # difference into an EQUIVALENT verdict.
    passed = all(
        result["identical"]["false_different_rate"] == 0.0
        and result["divergent"]["false_equivalent_rate"] == 0.0
        for result in results.values()
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
