"""Monte Carlo user-friction simulator for UAR onboarding.

This does not test API correctness. It estimates where users are likely to fail
while following the visual walkthrough.

Run:
    python tests/monte_carlo_user_sim.py
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from collections import Counter


@dataclass(frozen=True)
class Step:
    name: str
    base_success: float
    friction: str


STEPS = [
    Step("start_server", 0.82, "terminal/env setup"),
    Step("open_docs", 0.95, "browser/navigation"),
    Step("create_first_object", 0.88, "Swagger Try it out / JSON paste"),
    Step("copy_first_digest", 0.78, "copying sha256 digest"),
    Step("create_second_object", 0.90, "repeat object creation"),
    Step("copy_second_digest", 0.80, "copying sha256 digest"),
    Step("list_runtimes", 0.92, "finding GET /runtimes"),
    Step("execute_sum", 0.74, "replacing placeholder digests"),
    Step("run_workflow", 0.68, "multi-step JSON payload"),
    Step("trace_lineage", 0.72, "using finalOutput digest"),
]


def simulate_user(skill: float) -> tuple[bool, str | None]:
    """Return success/failure and failing step.

    skill ranges roughly from 0.0 to 1.0.
    Higher skill reduces friction.
    """
    for step in STEPS:
        adjusted_success = min(0.99, max(0.01, step.base_success + (skill - 0.5) * 0.25))
        if random.random() > adjusted_success:
            return False, step.name
    return True, None


def run_trials(n: int = 10_000, seed: int = 42) -> None:
    random.seed(seed)
    failures: Counter[str] = Counter()
    successes = 0

    for _ in range(n):
        # Beta distribution: most users are moderate, a few are very low/high skill.
        skill = random.betavariate(2.0, 2.0)
        ok, failed_step = simulate_user(skill)
        if ok:
            successes += 1
        else:
            failures[failed_step or "unknown"] += 1

    print("UAR Onboarding Monte Carlo")
    print("==========================")
    print(f"Trials: {n}")
    print(f"Successes: {successes} ({successes / n:.1%})")
    print(f"Failures: {n - successes} ({(n - successes) / n:.1%})")
    print()
    print("Top failure points:")
    for step, count in failures.most_common():
        friction = next(s.friction for s in STEPS if s.name == step)
        print(f"- {step}: {count} ({count / n:.1%}) — {friction}")

    print()
    print("Interpretation:")
    print("- The largest failure points should become UI helpers or clearer docs.")
    print("- If execute_sum/run_workflow dominate, add copy-paste templates.")
    print("- If digest-copy steps dominate, add UI affordances or clearer labels.")


if __name__ == "__main__":
    run_trials()
