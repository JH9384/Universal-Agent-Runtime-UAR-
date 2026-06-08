# D4D Evidence Index

> Status: focused D4C release gate passed locally  
> Scope: D4D validation, burn-in, and release-readiness evidence

---

## Purpose

This index collects the evidence locations needed to decide whether the D4C operator loop is promotable.

D4D remains validation-only.

---

## Primary Gate

Run:

```bash
make d4c-release-gate
```

This performs focused D4C validation and writes a local result stub.

Latest local focused gate result:

```text
D4C RELEASE GATE COMPLETE
```

Evidence file:

```text
docs/operations/validation-results/d4c-validation-2026-06-08T11-10-45Z.md
```

---

## Local Evidence

Validation result stubs are generated under:

```text
docs/operations/validation-results/
```

Template:

```text
docs/operations/D4D_VALIDATION_STATUS_TEMPLATE.md
```

Confirmed local evidence:

```text
docs/operations/validation-results/d4c-validation-2026-06-08T11-10-45Z.md
```

---

## CI Evidence

Workflow:

```text
.github/workflows/d4c-operator-loop.yml
```

Expected artifact:

```text
d4c-validation-${{ github.run_id }}
```

Expected file:

```text
validation.log
```

---

## Release Documents

- `docs/operations/D4D_VALIDATION_BURNIN_PLAN.md`
- `docs/operations/D4C_RELEASE_READINESS_SUMMARY.md`
- `docs/operations/D4C_RELEASE_PROMOTION_CHECKLIST.md`
- `docs/operations/D4C_RELEASE_NOTES_DRAFT.md`
- `RELEASE.md`
- `RELEASE_CHECKLIST.md`
- `CHANGELOG.md`

---

## Required Evidence Before Promotion

At least one validation result source:

- [x] local validation result file exists,
- [ ] CI validation artifact exists.

And all gates pass:

- [x] focused backend D4C tests,
- [x] focused frontend D4C tests,
- [x] frontend production build,
- [ ] broader regression or explicitly accepted decomposed checks.

---

## Anti-Sprawl Evidence

Confirm the release still does not add:

- [x] incident workbench,
- [x] new dashboard,
- [x] plugin registry,
- [x] incident store,
- [x] fleet store,
- [x] second trust score,
- [x] new evidence pipeline.

---

## Decision Record

Promotion decision should reference:

1. validation result file or CI artifact,
2. broader regression result,
3. release notes review,
4. explicit tag approval.

Do not tag from this index alone.

Current decision: focused gate passed; broader regression evidence is still required before promotion or tag approval.
