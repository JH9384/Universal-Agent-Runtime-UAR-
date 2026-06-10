# D4E Short Burn-In Sample

## Status

D4E short burn-in sample passed.

## Date

2026-06-09

## Command

```bash
python -m uar.cli.main burn-in run --mode=direct --suite=smoke --json
```

## Result

- Level: `smoke`
- Passed: `True`
- Score: `99`
- Error count: `0`
- Evidence count: `3`

## Scenario Evidence

- `api_reachable` — passed `True`, score `100`, detail: Registry has 127 skills
- `store_round_trip` — passed `True`, score `100`, detail: Stored and retrieved run burnin-smoke-1781058799646
- `replay_confidence` — passed `True`, score `96`, detail: Replay confidence Verified (score=96)

## Operational Meaning

This provides a short direct burn-in sample for D4E after repeat runtime smoke validation. It does not replace long-duration soak testing, but it confirms the burn-in runner, store round-trip, and replay-confidence scenario remain healthy in the D4E lane.

## Guardrails

- This is a short sample, not a 24h/72h soak.
- Full long-duration burn-in remains a later operational validation layer.
- No production runtime behavior is changed by this evidence record.
