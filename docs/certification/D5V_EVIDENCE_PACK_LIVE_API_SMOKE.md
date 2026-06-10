# D5V Evidence Pack Live API Smoke

## Status

D5V validates the Evidence Pack v2 endpoint against a running local UAR API.

## Endpoint

`GET /api/uar/evidence-pack/{run_id}`

## Run ID

`d5v-live-smoke`

## Commands Validated

```bash
curl -fsS -H "Authorization: Bearer local-admin-key" \
  "http://127.0.0.1:8000/api/uar/evidence-pack/d5v-live-smoke"

curl -fsS -H "Authorization: Bearer local-admin-key" \
  "http://127.0.0.1:8000/api/uar/evidence-pack/d5v-live-smoke?include_markdown=true"

curl -sS \
  "http://127.0.0.1:8000/api/uar/evidence-pack/d5v-live-smoke"
```

## Expected Results

- Authenticated basic request returns `status: ok`.
- `run_id` is preserved as `d5v-live-smoke`.
- Basic response returns `markdown: null`.
- Markdown-enabled response returns rendered Evidence Pack v2 Markdown.
- Unauthenticated request returns `unauthorized` with message `Authentication required`.

## Local Artifacts

Generated under ignored reports path:

- `reports/d5v/evidence_pack_basic.json`
- `reports/d5v/evidence_pack_markdown.json`
- `reports/d5v/evidence_pack_unauth.json`

## Validation Result

`D5V evidence pack live API smoke: PASS` after aligning the unauthenticated assertion to actual runtime behavior: `unauthorized`.

## Operational Meaning

Evidence Pack v2 is now validated through core tests, router tests, active API contract tests, and live authenticated API smoke.

## Guardrails

- Live smoke does not promote artifacts.
- Live smoke does not mutate outcomes, trust, runs, replay, burn-in, or certification.
- Reports remain ignored unless explicitly promoted.

## Runtime Correction

The first local assertion expected `authentication_required`, but the live API returned the existing UAR middleware shape:

```json
{
  "detail": {
    "error": "unauthorized",
    "message": "Authentication required"
  }
}
```

This is acceptable for D5V because the endpoint rejected unauthenticated access correctly. D5W should encode the actual runtime value: `unauthorized`.
