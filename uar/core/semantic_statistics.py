"""Distributional statistics for shadow-mode Semantic Replay validation.

This module is validation support, not a Trust Spine scoring component. It
provides small dependency-free statistics for repeated semantic traces and
shadow/non-shadow latency samples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Hashable, Iterable, Mapping, Sequence

from uar.core.semantic_trace import SemanticTrace, semantic_trace_hash


@dataclass(frozen=True, slots=True)
class DistributionalSemanticReport:
    baseline_samples: int
    candidate_samples: int
    js_divergence_bits: float
    total_variation: float
    baseline_entropy_bits: float
    candidate_entropy_bits: float
    mean_latency_delta: float | None = None
    p95_latency_delta: float | None = None

    @property
    def distribution_equivalent(self) -> bool:
        return self.js_divergence_bits == 0.0 and self.total_variation == 0.0


def empirical_distribution(
    values: Iterable[Hashable],
) -> Dict[Hashable, float]:
    counts: Dict[Hashable, int] = {}
    total = 0
    for value in values:
        counts[value] = counts.get(value, 0) + 1
        total += 1
    if total == 0:
        return {}
    return {key: count / total for key, count in counts.items()}


def entropy_bits(distribution: Mapping[Hashable, float]) -> float:
    return -sum(
        probability * math.log2(probability)
        for probability in distribution.values()
        if probability > 0.0
    )


def _kl_bits(
    left: Mapping[Hashable, float],
    right: Mapping[Hashable, float],
) -> float:
    out = 0.0
    for key, probability in left.items():
        if probability <= 0.0:
            continue
        reference = right.get(key, 0.0)
        if reference <= 0.0:
            return math.inf
        out += probability * math.log2(probability / reference)
    return out


def jensen_shannon_divergence_bits(
    left: Mapping[Hashable, float],
    right: Mapping[Hashable, float],
) -> float:
    """Symmetric finite divergence in bits, in [0, 1] for two distributions."""

    keys = set(left) | set(right)
    mixture = {
        key: 0.5 * left.get(key, 0.0) + 0.5 * right.get(key, 0.0)
        for key in keys
    }
    if not keys:
        return 0.0
    return 0.5 * _kl_bits(left, mixture) + 0.5 * _kl_bits(right, mixture)


def total_variation_distance(
    left: Mapping[Hashable, float],
    right: Mapping[Hashable, float],
) -> float:
    keys = set(left) | set(right)
    return 0.5 * sum(
        abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys
    )


def semantic_hash_distribution(
    traces: Iterable[SemanticTrace],
) -> Dict[str, float]:
    return empirical_distribution(
        semantic_trace_hash(trace) for trace in traces
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def compare_semantic_distributions(
    baseline_traces: Sequence[SemanticTrace],
    candidate_traces: Sequence[SemanticTrace],
    *,
    baseline_latencies: Sequence[float] = (),
    candidate_latencies: Sequence[float] = (),
) -> DistributionalSemanticReport:
    """Compare repeated semantic traces without imposing a Trust score.

    The caller should condition/stratify traces by task class and, when useful,
    by final result before calling this function.
    """

    baseline = semantic_hash_distribution(baseline_traces)
    candidate = semantic_hash_distribution(candidate_traces)

    mean_delta = None
    p95_delta = None
    if baseline_latencies and candidate_latencies:
        mean_delta = _mean(candidate_latencies) - _mean(baseline_latencies)
        p95_delta = _quantile(candidate_latencies, 0.95) - _quantile(
            baseline_latencies, 0.95
        )

    return DistributionalSemanticReport(
        baseline_samples=len(baseline_traces),
        candidate_samples=len(candidate_traces),
        js_divergence_bits=jensen_shannon_divergence_bits(baseline, candidate),
        total_variation=total_variation_distance(baseline, candidate),
        baseline_entropy_bits=entropy_bits(baseline),
        candidate_entropy_bits=entropy_bits(candidate),
        mean_latency_delta=mean_delta,
        p95_latency_delta=p95_delta,
    )


def version_information_bits(
    baseline_traces: Sequence[SemanticTrace],
    candidate_traces: Sequence[SemanticTrace],
) -> float:
    """Information an equal-prior version label carries via trace identity.

    For two equally likely versions this equals the Jensen-Shannon divergence
    between their semantic-trace distributions. Callers can approximate
    I(version; trace | result, task_class) by filtering to a result/task
    stratum before calling.
    """

    return compare_semantic_distributions(
        baseline_traces, candidate_traces
    ).js_divergence_bits


__all__ = [
    "DistributionalSemanticReport",
    "compare_semantic_distributions",
    "empirical_distribution",
    "entropy_bits",
    "jensen_shannon_divergence_bits",
    "semantic_hash_distribution",
    "total_variation_distance",
    "version_information_bits",
]
