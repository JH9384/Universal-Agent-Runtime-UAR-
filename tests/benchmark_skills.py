"""
Performance benchmarking script for skill execution times.

This script benchmarks the execution time of various skills to detect
performance regressions. Run this script before and after changes to
ensure performance hasn't degraded.
"""

import sys
import time
from pathlib import Path

from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.executor import Executor

sys.path.insert(0, str(Path(__file__).parent.parent))


class SkillBenchmark:
    """Benchmark skill execution performance"""

    def __init__(self):
        self.results = []

    def benchmark_hierarchical_vs_flat(
        self, goal, recipe_id="gr_query", iterations=10
    ):
        """Benchmark hierarchical (nested) vs flat recipe execution."""
        from uar.core.executor import Executor

        results = {"hierarchical": [], "flat": []}
        executor = Executor()

        for mode, flag in [("hierarchical", True), ("flat", False)]:
            for _ in range(iterations):
                strategy = StrategySpec(
                    goal_id="benchmark",
                    ordered_skills=[],
                )
                strategy.metadata = {"use_hierarchical": flag}
                start = time.time()
                list(
                    executor.iter_events(
                        strategy, goal, timeout_seconds=5.0
                    )
                )
                elapsed = time.time() - start
                results[mode].append(elapsed)

        self.results.append(
            {
                "skill": "hierarchical_vs_flat",
                "hierarchical_avg": sum(results["hierarchical"]) / iterations,
                "flat_avg": sum(results["flat"]) / iterations,
                "hierarchical_max": max(results["hierarchical"]),
                "flat_max": max(results["flat"]),
            }
        )
        return results

    def benchmark_cache_hit_vs_miss(self, goal, iterations=10):
        """Benchmark cache hit performance vs cache miss."""
        from uar.core.executor import Executor

        executor = Executor()
        # First call: cache miss
        miss_times = []
        for _ in range(iterations):
            strategy = StrategySpec(
                goal_id="benchmark",
                ordered_skills=["uor_ecosystem_status"],
            )
            start = time.time()
            list(executor.iter_events(strategy, goal, timeout_seconds=5.0))
            miss_times.append(time.time() - start)

        # Clear cache for comparison
        executor.recipe_cache.clear()
        hit_times = []
        for _ in range(iterations):
            strategy = StrategySpec(
                goal_id="benchmark",
                ordered_skills=["uor_ecosystem_status"],
            )
            start = time.time()
            list(executor.iter_events(strategy, goal, timeout_seconds=5.0))
            hit_times.append(time.time() - start)

        self.results.append(
            {
                "skill": "cache_hit_vs_miss",
                "miss_avg": sum(miss_times) / iterations,
                "hit_avg": sum(hit_times) / iterations,
                "miss_max": max(miss_times),
                "hit_max": max(hit_times),
            }
        )
        return {"miss": miss_times, "hit": hit_times}

    def benchmark_skill(self, skill_name, goal, timeout=30.0):
        """Benchmark a single skill execution"""
        strategy = StrategySpec(
            goal_id="benchmark",
            ordered_skills=[skill_name],
        )

        start_time = time.time()
        try:
            executor = Executor()
            events = list(
                executor.iter_events(strategy, goal, timeout_seconds=timeout)
            )
            elapsed = time.time() - start_time

            status = (
                "success"
                if events[-1]["payload"]["status"] == "completed"
                else "failed"
            )
            self.results.append(
                {
                    "skill": skill_name,
                    "elapsed_seconds": elapsed,
                    "status": status,
                    "event_count": len(events),
                }
            )
            return elapsed, status
        except Exception as e:
            elapsed = time.time() - start_time
            self.results.append(
                {
                    "skill": skill_name,
                    "elapsed_seconds": elapsed,
                    "status": f"error: {str(e)}",
                    "event_count": 0,
                }
            )
            return elapsed, f"error: {str(e)}"

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "=" * 60)
        print("SKILL PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"{'Skill':<30} {'Time (s)':<12} {'Status':<15}")
        print("-" * 60)

        for result in self.results:
            print(
                f"{result['skill']:<30} "
                f"{result['elapsed_seconds']:<12.3f} "
                f"{result['status']:<15}"
            )

        print("=" * 60)

        # Calculate statistics
        successful = [r for r in self.results if r["status"] == "success"]
        if successful:
            avg_time = sum(r["elapsed_seconds"] for r in successful) / len(
                successful
            )
            max_time = max(r["elapsed_seconds"] for r in successful)
            min_time = min(r["elapsed_seconds"] for r in successful)
            print(f"Average time (successful): {avg_time:.3f}s")
            print(f"Max time (successful): {max_time:.3f}s")
            print(f"Min time (successful): {min_time:.3f}s")


def main():
    """Run skill benchmarks"""
    print("=" * 60)
    print("UAR SKILL PERFORMANCE BENCHMARK")
    print("Measuring skill execution times for regression detection")
    print("=" * 60)

    benchmark = SkillBenchmark()

    # Benchmark available skills
    skills_to_benchmark = [
        "section_sum",
        "doc_ingest",
        # Note: Skip skills that require external services
        # (ollama, graphrag, autonomi) unless available
    ]

    goal = GoalSpec(
        id="benchmark", user_intent="benchmark", objective="Test goal"
    )

    for skill in skills_to_benchmark:
        print(f"\nBenchmarking: {skill}")
        elapsed, status = benchmark.benchmark_skill(skill, goal)
        print(f"  Time: {elapsed:.3f}s, Status: {status}")

    # Print summary
    benchmark.print_summary()

    # Save results to file for comparison
    import json

    with open("benchmark_results.json", "w") as f:
        json.dump(benchmark.results, f, indent=2)
    print("\nResults saved to benchmark_results.json")


if __name__ == "__main__":
    main()
