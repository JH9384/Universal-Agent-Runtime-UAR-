# Operator Entity Retention

UAR stores lightweight operator workflow entities through metadata keys.

| Namespace | Purpose | Discovery |
| --- | --- | --- |
| `operator:snapshot:*` | Time-machine / Mission Control snapshots | `list_meta_keys()` |
| `operator:incident:*` | Incident records | `list_meta_keys()` |
| `operator:inbox:*` | Recommendation inbox items | bounded fallback scan |
| `operator:investigation:*` | Investigation workflow records | bounded fallback scan |

## Snapshot Retention

Operator snapshots are retained under `operator:snapshot:*`.

The snapshot retention limit is **168 captures**, approximately hourly snapshots for one week.

On every snapshot persist, UAR attempts to prune older snapshots beyond the latest 168.

Retention requires both:

- `list_meta_keys()` for complete namespace discovery
- `delete_metadata()` or `delete_meta()` for real deletion

If complete key listing or deletion is unavailable, pruning becomes a safe no-op rather than risking partial deletion.

## Entity Health Endpoint

Operators can inspect metadata entity health through:

    GET /api/uar/operator/entity-health

The response should report backend metadata capabilities and per-entity discovery / retention status.

## Operational Meaning

This makes snapshot-retention safety visible to operators instead of relying only on implementation knowledge.
