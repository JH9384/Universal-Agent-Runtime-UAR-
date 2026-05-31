# UAR Runtime Baseline

## Runtime Identity

UAR immediate-side runtime baseline is:

```text
a deterministic, event-oriented, replayable execution substrate
```

The baseline now includes accepted visualization and math expansion already present on main.

---

## Accepted Baseline Components

### Runtime Substrate

```text
GoalSpec
PlannerRouter
RuntimeConfig
StrategySpec
Executor
RuntimeEvents
Replay Validation
RunRecord Reconstruction
Timeline Projection
Certification
```

### Accepted Expansion Baseline

```text
math_plot skill
3D/data visualization
MathPlotVisualizer
UARPanel integrations
runtime visualization support
```

These are now governed baseline components and must participate in burn-in.

---

## Execution Truth

Execution truth remains:

```text
RuntimeEvent trace
```

Derived structures:

```text
RunRecord
Replay summary
Timeline projection
Certification result
Visualization state
Operator UI
```

Derived structures must not redefine runtime truth.

---

## Baseline Burn-In Command

```bash
./scripts/burn_in.sh
```

Expected:

```text
runtime tests pass
visualization tests pass
make gate passes
no unreviewed semantic drift exists
```

---

## Baseline Principle

```text
Accept growth.
Govern growth.
Preserve execution truth.
```
