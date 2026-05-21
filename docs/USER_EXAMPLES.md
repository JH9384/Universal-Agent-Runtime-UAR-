# User Examples and Common Needs

This guide gives practical, copy-paste examples for users who want to get useful output from UAR quickly. It focuses on workflows that show the upgraded visual graph, metrics dashboard, and recipe timeline.

## How to Use These Examples

- **Web UI**: Open the UAR web app, choose a goal, select the listed skills or recipe, then run.
- **API**: Send the JSON payloads in `examples/user_payloads/` to `/api/uar/run` or `/api/uar/stream`.
- **Best first skill**: Use `doc_ingest` before analysis skills when you want UAR to inspect files.
- **Best graph skill**: Use `dependency_map` when you want the Dependency Graph panel to populate.

## Example 1: See a Codebase as a Graph

**User need**: “I want to understand how this project is connected.”

**Recommended skills**:

- `doc_ingest`
- `dependency_map`
- `sum_review`

**What to look at**:

- **Dependency Graph**: node clusters, hub node, density, groups.
- **Timeline**: skill order and completion status.
- **Metrics**: total runtime and per-skill timing.

**API payload**: `examples/user_payloads/codebase_graph.json`

## Example 2: Review Docs and Get Action Items

**User need**: “Tell me what is missing or unclear in these docs.”

**Recommended skills**:

- `doc_ingest`
- `ollama_generate`
- `sum_review`

**What to look at**:

- **Events**: verify docs were ingested before generation.
- **Metrics**: confirm LLM generation time versus ingestion time.

**API payload**: `examples/user_payloads/documentation_review.json`

## Example 3: Build a Searchable Knowledge Graph

**User need**: “Turn this folder into a knowledge graph I can query later.”

**Recommended skills**:

- `graphrag_index`

**What to look at**:

- **Timeline**: long-running indexing stages.
- **Metrics**: total time and cache behavior on repeated runs.

**API payload**: `examples/user_payloads/graphrag_index.json`

## Example 4: Query the Knowledge Graph

**User need**: “Ask questions across indexed documents.”

**Recommended skills**:

- `graphrag_query`

**Useful metadata**:

- `graphrag_method: local` for targeted questions.
- `graphrag_method: global` for themes and summaries.

**API payload**: `examples/user_payloads/graphrag_query.json`

## Example 5: Exercise Nested Recipes and Timeline Views

**User need**: “Show me recipe nesting, retries, and execution structure.”

Use the unified execution order payload to mix a recipe with standalone skills. This is best sent to `/api/uar/stream` so the UI can show recipe events as they happen.

**What to look at**:

- **Recipe Timeline**: nested indentation, retry badges, duration text.
- **Metrics Dashboard**: skill timings and cache hit/miss ratios.

**API payload**: `examples/user_payloads/nested_recipe_timeline.json`

## Example 6: UOR Object and Workflow Round Trip

**User need**: “Create content-addressed objects and run a workflow against them.”

Use UOR endpoints for object storage, runtime execution, lineage, and workflows.

**What to look at**:

- Object digests returned by `/api/uor/objects`.
- Workflow record digest from `/api/uor/workflows/run`.
- Lineage trace from `/api/uor/agents/lineage/trace`.

**Python example**: `examples/user_uor_workflow_example.py`

## Example 7: Visual Debugging Checklist

When a run does not look right:

1. **Open Timeline** and confirm the expected skills or recipes ran.
2. **Open Metrics** and check for slow or repeated skills.
3. **Open Dependency Graph** and inspect the hub node and disconnected groups.
4. **Export graph JSON** and confirm the graph has expected `nodes` and `edges`.
5. **Switch to JSON events** to inspect raw `recipe_start`, `skill_start`, `metrics`, and `orchestration_plan` events.

## Example 8: Which Workflow Should I Pick?

| Need | Start With | Add Later |
| --- | --- | --- |
| Understand a repo | `doc_ingest`, `dependency_map` | `sum_review` |
| Summarize docs | `doc_ingest`, `section_sum` | `ollama_generate` |
| Ask semantic questions | `graphrag_query` | `graphrag_index` first if needed |
| Build persistent knowledge | `graphrag_index` | `graphrag_query` |
| Inspect performance | Any streaming run | Metrics dashboard |
| Debug ordering | Recipes + streaming | Timeline JSON events |
| Store verifiable objects | UOR `/objects` | Lineage/workflow endpoints |

## Copy-Paste cURL Pattern

```bash
curl http://localhost:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d @examples/user_payloads/codebase_graph.json
```

For non-streaming runs:

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d @examples/user_payloads/documentation_review.json
```
