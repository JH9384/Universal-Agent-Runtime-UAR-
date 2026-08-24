"""End-to-end concurrent/stochastic Semantic Replay validation."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import random
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import uar.core.executor as executor_module
from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor
from uar.core.registry import registry
from uar.core.semantic_shadow import observe_runtime_semantics
from uar.core.semantic_statistics import (
    compare_semantic_distributions,
    empirical_distribution,
    jensen_shannon_divergence_bits,
    total_variation_distance,
)
from uar.core.semantic_trace import (
    project_nonsemantic_events,
    semantic_trace_from_events,
    validate_semantic_trace,
)

MIN_CONFIRMATORY_SAMPLES_PER_STRATUM = 200
MAX_P95_LATENCY_RATIO = 1.10
MAX_P99_LATENCY_RATIO = 1.15
MIN_THROUGHPUT_RATIO = 0.90
MAX_ORDER_JS_DIVERGENCE_BITS = 0.02
MAX_ORDER_TOTAL_VARIATION = 0.05
MAX_SEMANTIC_JS_DIVERGENCE_BITS = 0.02
MAX_SEMANTIC_TOTAL_VARIATION = 0.05

BRANCH_SKILLS = tuple(
    f"omega_concurrent_branch_{name}" for name in ("a", "b", "c", "d")
)
JOIN_SKILL = "omega_concurrent_join"


@dataclass(frozen=True, slots=True)
class Workload:
    name: str
    scheduler: str
    ordered_skills: tuple[str, ...]
    waves: tuple[tuple[str, ...], ...] | None


@dataclass(frozen=True, slots=True)
class RawRun:
    sample_id: int
    sample_seed: int
    runtime_seconds: float
    latency_seconds: float
    events: tuple[dict[str, Any], ...]
    shadow_events: tuple[dict[str, Any], ...] | None


def _register(name: str, function) -> None:
    if not registry.is_registered(name):
        registry.register(name, function)


def _branch_skill(name: str):
    def _run(ctx):
        metadata = getattr(ctx.goal, "metadata", {})
        delays = metadata.get("stochastic_delays", {})
        time.sleep(float(delays.get(name, 0.0)))
        return {
            "branch": name,
            "sample_token": metadata.get("sample_token"),
        }

    return _run


def _join_skill(ctx):
    metadata = getattr(ctx.goal, "metadata", {})
    return {
        "joined": sorted(name for name in BRANCH_SKILLS if name in ctx.data),
        "sample_token": metadata.get("sample_token"),
    }


def _register_workload_skills() -> None:
    for name in BRANCH_SKILLS:
        _register(name, _branch_skill(name))
    _register(JOIN_SKILL, _join_skill)


def _workloads() -> tuple[Workload, ...]:
    return (
        Workload(
            name="greedy_wide",
            scheduler="greedy",
            ordered_skills=BRANCH_SKILLS,
            waves=None,
        ),
        Workload(
            name="dag_diamond",
            scheduler="dag",
            ordered_skills=(*BRANCH_SKILLS, JOIN_SKILL),
            waves=(BRANCH_SKILLS, (JOIN_SKILL,)),
        ),
    )


def _delays(seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    ranks = list(range(1, len(BRANCH_SKILLS) + 1))
    rng.shuffle(ranks)
    return {
        name: (rank * 0.020) + rng.uniform(0.00020, 0.00080)
        for name, rank in zip(BRANCH_SKILLS, ranks)
    }


def _execute_one(
    workload: Workload,
    sample_id: int,
    sample_seed: int,
    side: str,
    with_shadow: bool,
) -> RawRun:
    goal = GoalSpec(
        id=f"semantic-concurrent-{workload.name}-{side}-{sample_id}",
        user_intent="measure concurrent semantic shadow behavior",
        objective="execute a stochastic production-shaped workload",
        metadata={
            "enable_cache": False,
            "enable_parallel": True,
            "sample_token": sample_seed,
            "stochastic_delays": _delays(sample_seed),
        },
    )
    strategy = StrategySpec(
        goal_id=goal.id,
        ordered_skills=list(workload.ordered_skills),
        waves=(
            [list(wave) for wave in workload.waves]
            if workload.waves is not None
            else None
        ),
    )
    started = time.perf_counter()
    events = tuple(
        Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=2.0,
            _run_id=f"semantic-concurrent-{side}-{sample_id}",
        )
    )
    runtime_seconds = time.perf_counter() - started
    shadow_events = observe_runtime_semantics(events) if with_shadow else None
    latency = time.perf_counter() - started
    return RawRun(
        sample_id=sample_id,
        sample_seed=sample_seed,
        runtime_seconds=runtime_seconds,
        latency_seconds=latency,
        events=events,
        shadow_events=shadow_events,
    )


def _run_batch(
    workload: Workload,
    samples: Iterable[tuple[int, int]],
    *,
    concurrency: int,
    side: str,
    with_shadow: bool,
) -> tuple[list[RawRun], float]:
    sample_list = list(samples)
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=concurrency
    ) as pool:
        futures = [
            pool.submit(
                _execute_one,
                workload,
                sample_id,
                sample_seed,
                side,
                with_shadow,
            )
            for sample_id, sample_seed in sample_list
        ]
        runs = [future.result() for future in futures]
    return runs, time.perf_counter() - started


def _quantile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _result_signature(events: Iterable[dict[str, Any]]) -> str:
    complete = next(
        event
        for event in reversed(tuple(events))
        if event.get("type") == "complete"
    )
    payload = complete.get("payload", {})
    outputs = payload.get("outputs", [])
    canonical_outputs = sorted(
        outputs,
        key=lambda value: json.dumps(value, sort_keys=True, default=str),
    )
    result = {
        "status": payload.get("status"),
        "outputs": canonical_outputs,
        "errors": sorted(payload.get("errors", [])),
        "final_context": payload.get("final_context", {}),
    }
    return json.dumps(result, sort_keys=True, default=str)


def _order_signature(events: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(
        str(event.get("skill"))
        for event in events
        if event.get("type") == "skill_complete"
        and event.get("skill") in BRANCH_SKILLS
    )


def _order_fidelity_distribution(
    runs: Iterable[RawRun],
) -> dict[bool, float]:
    """Pool pairwise agreement with each run's seeded delay ordering."""

    outcomes = []
    for run in runs:
        observed = _order_signature(run.events)
        positions = {skill: index for index, skill in enumerate(observed)}
        delays = _delays(run.sample_seed)
        for left_index, left in enumerate(BRANCH_SKILLS):
            for right in BRANCH_SKILLS[left_index + 1 :]:
                expected = delays[left] < delays[right]
                actual = positions[left] < positions[right]
                outcomes.append(actual == expected)
    return empirical_distribution(outcomes)


def _order_distribution_divergence(
    baseline_runs: list[RawRun],
    candidate_runs: list[RawRun],
) -> tuple[float, float]:
    baseline = _order_fidelity_distribution(baseline_runs)
    candidate = _order_fidelity_distribution(candidate_runs)
    return (
        jensen_shannon_divergence_bits(baseline, candidate),
        total_variation_distance(baseline, candidate),
    )


def _analyze_stratum(
    workload: Workload,
    concurrency: int,
    baseline_runs: list[RawRun],
    candidate_runs: list[RawRun],
) -> dict[str, Any]:
    baseline_by_id = {run.sample_id: run for run in baseline_runs}
    candidate_by_id = {run.sample_id: run for run in candidate_runs}
    sample_ids = sorted(set(baseline_by_id) & set(candidate_by_id))

    baseline_traces = []
    candidate_traces = []
    projection_mismatches = 0
    integrity_issues = 0
    result_mismatches = 0
    for sample_id in sample_ids:
        baseline = baseline_by_id[sample_id]
        candidate = candidate_by_id[sample_id]
        baseline_shadow = observe_runtime_semantics(baseline.events)
        candidate_shadow = candidate.shadow_events
        if candidate_shadow is None:
            raise AssertionError("candidate shadow is required")
        if project_nonsemantic_events(candidate_shadow) != candidate.events:
            projection_mismatches += 1
        baseline_trace = semantic_trace_from_events(baseline_shadow)
        candidate_trace = semantic_trace_from_events(candidate_shadow)
        baseline_traces.append(baseline_trace)
        candidate_traces.append(candidate_trace)
        integrity_issues += len(validate_semantic_trace(baseline_trace))
        integrity_issues += len(validate_semantic_trace(candidate_trace))
        if _result_signature(baseline.events) != _result_signature(
            candidate.events
        ):
            result_mismatches += 1

    baseline_latencies = [run.runtime_seconds for run in candidate_runs]
    candidate_latencies = [run.latency_seconds for run in candidate_runs]
    baseline_p95 = _quantile(baseline_latencies, 0.95)
    candidate_p95 = _quantile(candidate_latencies, 0.95)
    baseline_p99 = _quantile(baseline_latencies, 0.99)
    candidate_p99 = _quantile(candidate_latencies, 0.99)
    p95_ratio = candidate_p95 / baseline_p95
    p99_ratio = candidate_p99 / baseline_p99
    baseline_throughput = len(candidate_runs) / sum(baseline_latencies)
    candidate_throughput = len(candidate_runs) / sum(candidate_latencies)
    throughput_ratio = candidate_throughput / baseline_throughput

    baseline_order_samples = [
        _order_signature(run.events) for run in baseline_runs
    ]
    candidate_order_samples = [
        _order_signature(run.events) for run in candidate_runs
    ]
    baseline_orders = empirical_distribution(baseline_order_samples)
    candidate_orders = empirical_distribution(candidate_order_samples)
    order_js, order_tv = _order_distribution_divergence(
        baseline_runs, candidate_runs
    )
    semantic = compare_semantic_distributions(
        baseline_traces,
        candidate_traces,
        baseline_latencies=baseline_latencies,
        candidate_latencies=candidate_latencies,
    )

    passed = (
        projection_mismatches == 0
        and result_mismatches == 0
        and integrity_issues == 0
        and p95_ratio <= MAX_P95_LATENCY_RATIO
        and p99_ratio <= MAX_P99_LATENCY_RATIO
        and throughput_ratio >= MIN_THROUGHPUT_RATIO
        and order_js <= MAX_ORDER_JS_DIVERGENCE_BITS
        and order_tv <= MAX_ORDER_TOTAL_VARIATION
        and semantic.js_divergence_bits <= MAX_SEMANTIC_JS_DIVERGENCE_BITS
        and semantic.total_variation <= MAX_SEMANTIC_TOTAL_VARIATION
    )
    return {
        "workload": workload.name,
        "scheduler": workload.scheduler,
        "concurrency": concurrency,
        "samples": len(sample_ids),
        "passed": passed,
        "projection_mismatches": projection_mismatches,
        "result_mismatches": result_mismatches,
        "integrity_issues": integrity_issues,
        "latency_seconds": {
            "baseline_p95": baseline_p95,
            "candidate_p95": candidate_p95,
            "p95_ratio": p95_ratio,
            "baseline_p99": baseline_p99,
            "candidate_p99": candidate_p99,
            "p99_ratio": p99_ratio,
        },
        "throughput_runs_per_second": {
            "comparison": "paired per-run work seconds",
            "baseline": baseline_throughput,
            "candidate": candidate_throughput,
            "ratio": throughput_ratio,
        },
        "scheduler_order": {
            "comparison": "pooled pairwise seeded-delay fidelity",
            "baseline_distinct_orders": len(baseline_orders),
            "candidate_distinct_orders": len(candidate_orders),
            "js_divergence_bits": order_js,
            "total_variation": order_tv,
        },
        "semantic_distribution": {
            "js_divergence_bits": semantic.js_divergence_bits,
            "total_variation": semantic.total_variation,
            "baseline_entropy_bits": semantic.baseline_entropy_bits,
            "candidate_entropy_bits": semantic.candidate_entropy_bits,
        },
    }


def _reset_coalescing_state() -> None:
    with executor_module._coalesce_meta_lock:
        executor_module._coalesce_results.clear()
        executor_module._coalesce_lru.clear()


def _run_stratum(
    workload: Workload,
    concurrency: int,
    samples_per_stratum: int,
    seed: int,
) -> dict[str, Any]:
    old_scheduler = executor_module._UAR_SCHEDULER
    executor_module._UAR_SCHEDULER = workload.scheduler
    baseline_runs: list[RawRun] = []
    candidate_runs: list[RawRun] = []
    try:
        warmup = [(-1, seed - 1)]
        _run_batch(
            workload,
            warmup,
            concurrency=1,
            side="warmup-baseline",
            with_shadow=False,
        )
        _run_batch(
            workload,
            warmup,
            concurrency=1,
            side="warmup-candidate",
            with_shadow=True,
        )

        samples = [
            (sample_id, seed + sample_id)
            for sample_id in range(samples_per_stratum)
        ]
        for batch_index, offset in enumerate(
            range(0, samples_per_stratum, concurrency)
        ):
            batch = samples[offset : offset + concurrency]
            sides = ("baseline", "candidate")
            if batch_index % 2:
                sides = tuple(reversed(sides))
            for side in sides:
                _reset_coalescing_state()
                runs, _ = _run_batch(
                    workload,
                    batch,
                    concurrency=concurrency,
                    side=side,
                    with_shadow=side == "candidate",
                )
                if side == "baseline":
                    baseline_runs.extend(runs)
                else:
                    candidate_runs.extend(runs)
    finally:
        executor_module._UAR_SCHEDULER = old_scheduler

    return _analyze_stratum(
        workload,
        concurrency,
        baseline_runs,
        candidate_runs,
    )


def build_report(
    *,
    mode: str,
    samples_per_stratum: int,
    seed: int,
    concurrency_levels: tuple[int, ...],
) -> dict[str, Any]:
    if mode not in {"pilot", "confirmatory"}:
        raise ValueError("mode must be pilot or confirmatory")
    if samples_per_stratum < 1:
        raise ValueError("samples_per_stratum must be positive")
    if mode == "confirmatory" and (
        samples_per_stratum < MIN_CONFIRMATORY_SAMPLES_PER_STRATUM
    ):
        raise ValueError(
            "confirmatory mode requires at least "
            f"{MIN_CONFIRMATORY_SAMPLES_PER_STRATUM} samples per stratum"
        )

    _register_workload_skills()
    strata = []
    for workload_index, workload in enumerate(_workloads()):
        for concurrency in concurrency_levels:
            stratum_seed = seed + (workload_index * 100_000) + concurrency
            strata.append(
                _run_stratum(
                    workload,
                    concurrency,
                    samples_per_stratum,
                    stratum_seed,
                )
            )

    threshold_passed = all(item["passed"] for item in strata)
    return {
        "schema": "uar.semantic-shadow-concurrent-review.v1",
        "mode": mode,
        "gate_enforced": mode == "confirmatory",
        "seed": seed,
        "samples_per_stratum": samples_per_stratum,
        "thresholds": {
            "min_confirmatory_samples_per_stratum": (
                MIN_CONFIRMATORY_SAMPLES_PER_STRATUM
            ),
            "max_p95_latency_ratio": MAX_P95_LATENCY_RATIO,
            "max_p99_latency_ratio": MAX_P99_LATENCY_RATIO,
            "min_throughput_ratio": MIN_THROUGHPUT_RATIO,
            "max_order_js_divergence_bits": (MAX_ORDER_JS_DIVERGENCE_BITS),
            "max_order_total_variation": MAX_ORDER_TOTAL_VARIATION,
            "max_semantic_js_divergence_bits": (
                MAX_SEMANTIC_JS_DIVERGENCE_BITS
            ),
            "max_semantic_total_variation": (MAX_SEMANTIC_TOTAL_VARIATION),
            "projection_mismatches": 0,
            "result_mismatches": 0,
            "integrity_issues": 0,
        },
        "threshold_passed": threshold_passed,
        "passed": threshold_passed if mode == "confirmatory" else True,
        "strata": strata,
    }


def _parse_concurrency(value: str) -> tuple[int, ...]:
    levels = tuple(int(item) for item in value.split(",") if item.strip())
    if not levels or any(level < 1 for level in levels):
        raise argparse.ArgumentTypeError(
            "concurrency must contain positive comma-separated integers"
        )
    return levels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("pilot", "confirmatory"), default="confirmatory"
    )
    parser.add_argument("--samples-per-stratum", type=int, default=200)
    parser.add_argument("--seed", type=int, default=8191)
    parser.add_argument(
        "--concurrency",
        type=_parse_concurrency,
        default=(1, 4, 16, 32),
    )
    args = parser.parse_args()
    report = build_report(
        mode=args.mode,
        samples_per_stratum=args.samples_per_stratum,
        seed=args.seed,
        concurrency_levels=args.concurrency,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
