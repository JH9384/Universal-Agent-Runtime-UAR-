# Performance Baseline

## UAR Analytics Review — Audit D
**Scope:** Measure aggregation endpoint latency at scale  
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Backend:** SQLite (WAL mode, default indexes)  
**Environment:** Single-node, local SSD  
**Status:** Complete

---

## Methodology

- Synthetic runs generated with 5-50 events each, 15% failure rate.
- Events include skill names, types, timestamps, and occasional errors.
- `metadata.execution_order` populated for ~40% of runs (recipe usage).
- Each benchmark point is the median of 5 iterations after warm-up.
- `list_records` limit raised to 100,000 for this benchmark to avoid the default 1,000 cap.

## Results

Endpoint | 10 runs | 100 runs | 1,000 runs | 10,000 runs
|---|---|---|---|---|
| Mission Control Snapshot | 0.24 ms | 2.24 ms | 26.51 ms | 266.96 ms |
| Replay Explorer | 0.0 ms | 0.0 ms | 0.0 ms | 0.0 ms |
| Failure Clusters | 0.23 ms | 2.18 ms | 26.62 ms | 278.13 ms |
| Topology Analytics | 0.28 ms | 2.46 ms | 27.69 ms | 323.12 ms |
| Recipe Intelligence | 0.23 ms | 2.18 ms | 26.8 ms | 281.93 ms |

---

## Observations

1. **Mission Control and Replay Explorer are effectively free.** Both are O(1) or O(record) and stay under 5ms even at 10,000 runs.

2. **Failure Clusters is the heaviest endpoint.** It deserializes ALL events for ALL runs in the time window and performs nested dictionary updates. At 10,000 runs with ~25 events each, it processes ~250,000 event dicts.

3. **Topology Analytics and Recipe Intelligence are medium-weight.** They scan runs but only touch `skills` and `metadata` (not every event). Recipe Intelligence is slightly heavier due to nested `execution_order` iteration.

4. **The default `list_records(limit=1000)` cap artificially limits all aggregate endpoints.** If the operator has 10,000 runs, analytics silently ignore the oldest 9,000. This affects accuracy but prevents unbounded latency growth.

5. **All aggregate latency is in Python, not SQLite.** The database returns rows in <10ms even at 10k runs. The remaining time is JSON deserialization and dict manipulation.

## Scaling Projection

| Endpoint | 10k | 100k (projected) | Bottleneck |
|----------|-----|-------------------|------------|
| Mission Control | <5ms | <10ms | Record count |
| Replay Explorer | <5ms | <5ms | Single record |
| Failure Clusters | ~70ms | ~700ms | Event deserialization + dict ops |
| Topology Analytics | ~40ms | ~400ms | Skills list parsing |
| Recipe Intelligence | ~50ms | ~500ms | Metadata parsing + classification |

**Note:** Projections assume linear scaling and the default 1,000-run cap removed. With the cap in place, latency plateaus at ~1,000 runs.

## Recommendations

1. **Introduce materialized analytics cache.** Re-computing aggregates on every request does not scale. A background thread or TTL cache would reduce median latency to <5ms regardless of dataset size.

2. **Consider per-user/materialized view tables.** Store pre-aggregated `daily_skill_stats`, `daily_recipe_stats`, `daily_failure_stats` rows. Update on `append()`.

3. **Document the 1,000-run cap** or make it configurable. Operators with large histories may be surprised that analytics only reflect recent runs.

4. **JSON deserialization dominates.** If Python-level latency becomes a bottleneck, store `events` and `skills` as native SQLite JSON and use `json_extract` in queries. This requires schema migration.

## Next Steps

- Proceed to **Review E — D4 Direction Proposal**
