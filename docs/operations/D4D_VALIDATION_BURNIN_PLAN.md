# D4D — Release Validation & Operational Burn-In

> Status: phase scaffolded  
> Scope: validation, burn-in, and promotion readiness only

---

## Purpose

D4D turns the D4C operator loop from implemented into validated and promotable.

D4D does not add product surface.

Current spine under validation:

```text
Fleet Signal Spine → Operator Loop → Incident Recurrence → Evidence Preview → Export / Artifact Support → Release Gate Docs
```

---

## Phase Goals

1. Run the focused D4C release gate.
2. Capture validation evidence.
3. Fix only validation failures.
4. Run broader regression if the focused gate passes.
5. Prepare explicit release/tag decision material.

---

## D4D-1 — Focused Gate

Run:

```bash
make d4c-release-gate
```

Expected:

- backend D4C regression slice passes,
- frontend D4C tests pass,
- frontend production build passes,
- validation result stub is generated.

---

## D4D-2 — Failure Fix Policy

Only fix validation failures.

Allowed fix categories:

- broken test,
- broken build,
- broken Mission Control payload,
- broken replay handoff,
- broken outcome capture,
- broken Evidence Markdown export,
- docs/checklist mismatch.

Do not add new product features.

---

## D4D-3 — Broader Regression

After the focused gate passes, run either:

```bash
make test-regression
```

or the decomposed path:

```bash
make test-backend
make test-frontend
make build-frontend
```

---

## D4D-4 — Evidence Capture

At least one must exist before promotion:

- CI artifact: `d4c-validation-${{ github.run_id }}` containing `validation.log`,
- local validation result under `docs/operations/validation-results/`.

---

## D4D-5 — Release Decision

Only after gates pass:

1. update release notes if needed,
2. confirm anti-sprawl criteria,
3. request explicit tag approval,
4. tag only after approval.

---

## Non-Goals

Do not add:

- incident workbench,
- new dashboard,
- plugin registry,
- incident store,
- fleet store,
- second trust score,
- new evidence pipeline.
