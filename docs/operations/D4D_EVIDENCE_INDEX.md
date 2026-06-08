# D4D Evidence Index

> Status: evidence index scaffolded  
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

- [ ] local validation result file exists,
- [ ] CI validation artifact exists.

And all gates pass:

- [ ] focused backend D4C tests,
- [ ] focused frontend D4C tests,
- [ ] frontend production build,
- [ ] broader regression or explicitly accepted decomposed checks.

---

## Anti-Sprawl Evidence

Confirm the release still does not add:

- [ ] incident workbench,
- [ ] new dashboard,
- [ ] plugin registry,
- [ ] incident store,
- [ ] fleet store,
- [ ] second trust score,
- [ ] new evidence pipeline.

---

## Decision Record

Promotion decision should reference:

1. validation result file or CI artifact,
2. broader regression result,
3. release notes review,
4. explicit tag approval.

Do not tag from this index alone.
