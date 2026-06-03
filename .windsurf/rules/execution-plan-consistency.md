---
description: Executor must use pre-computed waves from orchestration plan; do not recompute
tags: [bug-pattern, executor, scheduling, dag, python]
globs: ["uar/**/*.py"]
---

# Execution Plan Consistency Rule

## Rule

If an orchestration plan pre-computes execution waves and attaches them to the strategy, the executor MUST use those waves directly. It MUST NOT recompute waves with a different algorithm that may produce different groupings.

**Forbidden:**
```python
# GoalExecutionService builds waves with greedy algorithm
plan = build_orchestration_plan(strategy, deps)
strategy.waves = plan.waves

# Executor ignores strategy.waves and recomputes with Kahn's algorithm
skill_groups = dag_schedule(strategy.ordered_skills, registry)
```

**Correct:**
```python
if _UAR_SCHEDULER == "dag" and enable_parallel:
    if strategy.waves:
        skill_groups = list(strategy.waves)
    else:
        skill_groups = dag_schedule(strategy.ordered_skills, registry)
```

## Why

Recomputing waves with a different algorithm causes the **UI to show a different plan than what actually executes**. The orchestration plan is streamed to the client first as a contract; silently changing the grouping breaks observability and makes debugging impossible.

## Detect

Look for places where `strategy.waves` is set but later ignored in favor of a fresh computation. Also look for `except Exception:` swallowing `CircularDependencyError` — the cycle information is critical for the client to understand why execution failed.

## Exception

Recomputation is acceptable when `strategy.waves` is explicitly `None` or empty and the executor is in a standalone mode (e.g., CLI batch runner) where no orchestration plan was built.
