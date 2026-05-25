# UOR Upstream Artifacts

This directory pins the upstream **UOR-Foundation/UOR-Framework** release our runtime targets for compatibility validation.

- **Upstream release:** `v0.5.2` (published 2026-05-23)
- **Source:** https://github.com/UOR-Foundation/UOR-Framework/releases/tag/v0.5.2
- **Artifacts:** JSON-LD, Turtle, N-Triples, OWL, JSON Schema, SHACL shapes, grammar, and the Linux binary bundle.

## How to refresh

Use the helper script to download and verify all assets:

```bash
python scripts/fetch_uor_artifacts.py --tag v0.5.2
```

Artifacts are stored under `third_party/uor/cache/<tag>/` and validated against the SHA-256 digests in [`DIGESTS.json`](./DIGESTS.json). CI should fail if any digest drifts, ensuring we always know exactly which upstream schema we validate against.

If the UOR Foundation publishes a newer release:

1. Update `VERSION` to the new tag.
2. Update the digests in `DIGESTS.json` (available from the release metadata).
3. Run the fetch script and commit the refreshed artifacts (or keep them ignored but reproducible).
4. Update docs/tests to reference the new tag and re-run compatibility validation.
