# D4H Release Validation Checklist

## Status

D4H release validation checklist is the operator-facing consolidation checklist after D4G CI verification.

## Authoritative Gates

1. D4D final validation closure exists.
2. D4E runtime smoke passes locally through `make d4e-runtime-smoke`.
3. D4F CI runtime smoke passes in GitHub Actions.
4. D4G CI regression gates pass in GitHub Actions.
5. Authoritative D4G tag exists: `v1.2.8-d4g-ci-verified`.

## Local Operator Commands

```bash
make d4e-runtime-smoke
ruff check .
ulimit -n 8192
```

## CI Workflows

- `.github/workflows/d4e-runtime-smoke.yml`
- `.github/workflows/d4g-regression.yml`

## Known Non-Blocking Items

- Docker smoke is deferred when Docker daemon is unavailable.
- The historical Node 20 action warning is addressed on the maintained
  workflows; confirm its absence in the next release run.
- CI uses Python `3.12` because package metadata requires `<3.13,>=3.10`.

## Tag Authority

- D4F: `v1.2.5-d4f-ci-smoke`
- D4G: `v1.2.8-d4g-ci-verified`

## Guardrails

- Do not weaken warning gates.
- Do not delete premature tags; supersede them in documentation.
- Do not add runtime features during release validation consolidation.
