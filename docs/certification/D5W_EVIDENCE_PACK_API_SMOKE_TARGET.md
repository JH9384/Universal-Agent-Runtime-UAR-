# D5W Evidence Pack API Smoke Target

## Status

D5W adds a repeatable Evidence Pack v2 live API smoke script and Make target.

## Script

`scripts/evidence_pack/validate_evidence_pack_api_smoke.sh`

## Make Target

```bash
make d5w-evidence-pack-api-smoke
```

## Validated Behavior

- API health preflight must pass.
- Authenticated basic Evidence Pack request returns `status: ok`.
- Run identity is preserved.
- Basic response returns `markdown: null`.
- Markdown-enabled response returns rendered Evidence Pack v2 Markdown.
- Unauthenticated request returns existing runtime auth shape: `unauthorized` / `Authentication required`.
- Summary artifact is written under `reports/d5w/summary.json`.

## Validation Result

`D5W evidence pack API smoke: PASS`

## Guardrails

- Generated reports remain ignored unless explicitly promoted.
- The smoke target does not mutate outcomes, trust, runs, replay, burn-in, or certification.
- The smoke target does not promote artifacts.
- The endpoint remains authenticated and read-only.
