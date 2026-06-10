# D4F CI Runtime Smoke Baseline

## Status

D4F CI runtime smoke validation passed.

## Date

2026-06-09

## Workflow

`.github/workflows/d4e-runtime-smoke.yml`

## Trigger

GitHub Actions `workflow_dispatch`

## Runtime Decision

- CI Python: `3.12`
- Reason: package metadata currently requires `<3.13,>=3.10`
- Prior failed attempt: Python `3.14.5` installed successfully on GitHub-hosted runner, but package install was rejected by metadata.

## Validation Command

```bash
make d4e-runtime-smoke
```

## Expected Pass Output

```text
D4E runtime smoke: PASS
```

## Operational Meaning

D4F promotes the D4E local runtime smoke lane into a CI-visible release validation gate.

## Guardrails

- Docker smoke remains deferred unless Docker daemon availability is confirmed.
- Generated `reports/d4e/` artifacts are uploaded by CI but remain ignored locally.
- No production runtime behavior is changed by this evidence record.
