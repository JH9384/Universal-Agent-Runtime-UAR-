# D4F Runtime Smoke Validation Workflow

## Status

D4F is the follow-on lane after D4E runtime smoke validation.

## Source Evidence

D4E closed the repeatable runtime smoke lane with:

- `scripts/validate_d4e_runtime_smoke.sh`
- `scripts/d4e/write_runtime_smoke_summary.py`
- `docs/certification/D4E_RUNTIME_SMOKE_BASELINE.md`
- `docs/certification/D4E_RUNTIME_SMOKE_CLOSURE.md`
- `docs/certification/D4E_DOCKER_SMOKE_DECISION.md`
- `docs/certification/D4E_SHORT_BURNIN_SAMPLE.md`

## Objective

Promote runtime smoke validation from a successful evidence script into a normal operator and release validation workflow.

## GitHub Tracking

- D4F issue: `#119`
- D5A productization issue: `#120`

## Workflow Target

A single operator command should validate:

1. API boot
2. health endpoint readiness
3. Mission Control JSON capture
4. certification JSON capture
5. API burn-in run
6. latest burn-in retrieval
7. runtime smoke summary artifact generation
8. clean API shutdown

## Proposed Make Target

```bash
make d4e-runtime-smoke
```

The make target should call:

```bash
./scripts/validate_d4e_runtime_smoke.sh
```

## CI Decision Point

D4F runtime smoke is now promoted to a CI-visible workflow.

Workflow:

- `.github/workflows/d4e-runtime-smoke.yml`

Hosted-runner compatibility finding:

- Python `3.14.5` is available on GitHub-hosted runners.
- UAR package metadata currently requires `<3.13,>=3.10`.
- Therefore the D4E/D4F CI smoke lane uses Python `3.12`.
- Local D4D/D4E evidence remains recorded against Python `3.14.5`.

Docker smoke remains deferred until Docker daemon availability is confirmed.

## Acceptance Criteria

- Runtime smoke can be reproduced without heredocs.
- Runtime smoke can be run without two terminal sessions.
- Generated artifacts stay under `reports/d4e/`.
- Generated artifacts remain ignored unless explicitly promoted.
- The workflow preserves the D4D/D4E validation guardrails.

## Guardrails

- Do not create a second smoke framework.
- Do not make Docker availability a hard blocker on hosts without Docker.
- Keep Mission Control, certification, burn-in, and replay evidence connected.
