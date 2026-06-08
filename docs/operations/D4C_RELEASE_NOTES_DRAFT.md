# D4C Release Notes Draft

> Status: draft pending validation  
> Scope: fleet/operator/recurrence/evidence spine

---

## Summary

This release arc adds a reuse-first D4C operator loop to UAR Mission Control.

The delivered spine is:

```text
Fleet Signal Spine → Operator Loop → Incident Recurrence → Evidence Preview → Export/Artifact Support
```

The work intentionally avoids creating a second operations product. Existing Mission Control, Replay Explorer, recommendation outcomes, trust movement, and Artifacts surfaces are reused.

---

## Highlights

### Operator daily loop

- Added Briefing as the primary operator entry point.
- Added Focus as the simplified operator view.
- Reused Mission Control data for operator context.
- Added direct Replay handoff from Briefing, Focus, and recurrence views.

### Fleet signal spine

- Added fleet signal construction and summary support.
- Added fleet linkage for replay, incident IDs, recommendation IDs, and evidence refs.
- Added AlertBanner support for fleet surfacing.

### Outcome capture

- Added recommendation outcome capture inside the existing operator flow.
- Reused `/api/uar/recommendations/outcome`.
- Avoided a fleet-specific outcome table or trust score.

### Incident recurrence intelligence

- Added incident recurrence summary from existing run records.
- Added recurrence surfacing in Briefing and Focus.
- Added compact recurrence notes.
- Added recurrence evidence refs and Replay handoff.

### Evidence support

- Added Evidence Pack v2 composition.
- Added fleet evidence and incident recurrence evidence sections.
- Added recurrence-aware Evidence Pack preview in the existing Artifacts tab.
- Added copy and download support for Evidence Markdown.

### Validation support

- Added focused D4C validation script.
- Added `make validate-d4c`.
- Added `make d4c-result`.
- Added `make d4c-release-gate`.
- Added GitHub Actions D4C validation workflow.
- Added CI validation log artifact capture.

---

## Validation Required Before Release

Run:

```bash
make d4c-release-gate
```

Then review or complete the generated validation result under:

```text
docs/operations/validation-results/
```

CI should also produce:

```text
d4c-validation-${{ github.run_id }}
```

with:

```text
validation.log
```

---

## Explicitly Not Added

This arc intentionally does not add:

- incident console,
- incident store,
- incident workbench,
- new dashboard,
- duplicate endpoint,
- second trust score,
- parallel evidence pipeline,
- plugin registry.

---

## Release Decision

Do not tag until:

- focused D4C gate passes,
- validation evidence is captured,
- anti-sprawl criteria are confirmed,
- broader regression is run if desired,
- explicit approval is given.
