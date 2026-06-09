# D4D Burn-In Baseline Evidence

## Purpose

This document captures the D4D burn-in baseline established by PR #113.

It exists so the proof of readiness is not trapped inside a transient pull request discussion or a single GitHub Actions run.

## What D4D proves

D4D proves that UAR has a repeatable, evidence-producing burn-in gate for the current runtime baseline.

The accepted baseline includes:

```text
runtime substrate tests
replay and certification tests
timeline projection tests
accepted math_plot baseline test
full Python suite execution
frontend dependency metadata diagnostics
frontend install evidence
burn-in script evidence
```

## What D4D does not prove

D4D does not claim that every future runtime expansion is certified.

It does not introduce or certify:

```text
new observer systems
DSE overlays
semantic scoring
symbolic overlays
memory graph cognition
multi-agent orchestration
new runtime semantics
```

Those remain out of scope unless separately proposed, tested, and documented.

## Canonical command

```bash
./scripts/burn_in.sh
```

The script is intentionally boring and repeatable. It is the operator-facing entry point for baseline burn-in.

## Workflow gate

```text
.github/workflows/runtime-burn-in.yml
```

The workflow validates:

```text
Python runtime install
frontend dependency metadata
apps/web deterministic install
canonical burn-in script
full pytest suite
artifact upload
```

## Evidence artifacts

Runtime Burn-In uploads:

```text
frontend-dependency-diagnostics
npm-install-log
burn-in-script-log
full-pytest-log
```

UAR CI frontend lanes upload:

```text
web-npm-ci-log
web-test-log
web-build-log
operator-dashboard-npm-ci-log
operator-dashboard-test-log
operator-dashboard-build-log
web-svelte-npm-ci-log
web-svelte-test-log
web-svelte-build-log
web-svelte-check-log
```

burnin-hardening uploads:

```text
hardening-tests-log
ordering-stress-log
hardening-gate-log
burnin-artifacts
```

## OpenAPI schema stabilization note

PR #113 may temporarily exclude legacy operational routers from OpenAPI schema generation while keeping their runtime routes mounted.

This is a D4D stabilization measure, not a permanent API documentation strategy.

Current temporary exclusions are tracked in issue #116 and should be removed after schema normalization:

```text
uar/api/routers/uor.py
uar/api/routers/fleet.py
```

Reason:

```text
Some legacy operational routers use broad dictionary annotations such as Dict[str, Any]
and List[Dict[str, Any]] with postponed annotations. Under randomized test import
order, FastAPI/Pydantic v2 can surface unresolved TypeAdapter forward references
while generating /openapi.json.
```

Required follow-up:

```text
Replace broad dict request/response annotations with explicit Pydantic models or stable builtin dict annotations.
Add targeted OpenAPI tests for the legacy operational routers.
Re-enable those routers in OpenAPI after /openapi.json is stable under randomized order.
```

## Current known follow-ups

The following are intentionally tracked as follow-up work rather than hidden inside the D4D baseline:

```text
#114 Replace npm ci --legacy-peer-deps with true React dependency alignment.
#115 Add real smoke/component tests to apps/web-svelte and remove --passWithNoTests.
#116 Normalize OpenAPI schemas for legacy operational routers and remove temporary schema exclusions.
Review any ordering-stress failure using ordering-stress-log before changing runtime semantics.
```

## Merge readiness rule

D4D is ready only when the current PR head has:

```text
Runtime Burn-In passing
UAR CI passing or any failure explicitly reviewed
burnin-hardening passing or ordering-stress evidence reviewed
PR mergeable true
PR no longer draft
```

## Operational reading

```text
Boring is the point.
Evidence before interpretation.
Artifacts before guesses.
RuntimeEvent trace remains execution truth.
```
