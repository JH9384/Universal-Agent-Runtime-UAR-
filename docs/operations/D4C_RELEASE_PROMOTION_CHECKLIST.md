# D4C Release Promotion Checklist

> Status: pre-promotion checklist  
> Scope: D4C fleet/operator/recurrence/evidence spine

---

## Purpose

This checklist defines what must be true before promoting the D4C operator loop as release-ready.

It does not tag or publish a release by itself.

---

## Required Gate

Run:

```bash
make d4c-release-gate
```

This runs focused D4C validation and writes a validation result stub.

---

## Required Evidence

Before promotion, confirm at least one of:

- CI D4C workflow passed and uploaded `d4c-validation-${{ github.run_id }}` artifact,
- local `make d4c-release-gate` passed and a validation result was recorded under `docs/operations/validation-results/`.

---

## Promotion Criteria

All must be true:

- [ ] focused backend D4C tests passed,
- [ ] focused frontend D4C tests passed,
- [ ] frontend production build passed,
- [ ] Mission Control exposes `fleet_summary`,
- [ ] Mission Control exposes `incident_summary`,
- [ ] Briefing surfaces fleet/recurrence context,
- [ ] Focus surfaces fleet/recurrence context,
- [ ] Replay handoff works from Briefing, Focus, and recurrence,
- [ ] outcome capture uses `/api/uar/recommendations/outcome`,
- [ ] Artifacts surfaces Evidence Pack preview,
- [ ] Evidence markdown copy works,
- [ ] Evidence markdown download works,
- [ ] CI artifact capture is configured.

---

## Anti-Sprawl Criteria

All must remain true:

- [ ] no incident console,
- [ ] no incident store,
- [ ] no duplicate endpoint,
- [ ] no new dashboard,
- [ ] no parallel workflow,
- [ ] no second trust score,
- [ ] no parallel evidence pipeline,
- [ ] no plugin registry introduced for this arc.

---

## If Any Gate Fails

Do not promote.

Instead:

1. record the failure in the validation result,
2. fix the smallest failing slice,
3. rerun `make d4c-release-gate`,
4. re-check anti-sprawl criteria.

---

## If All Gates Pass

Next eligible action:

1. run broader regression if desired,
2. update release notes,
3. tag only after explicit approval.

Do not tag automatically from this checklist.
