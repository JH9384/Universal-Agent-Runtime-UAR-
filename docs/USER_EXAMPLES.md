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

## Example 7: Guardrails and Governance Check

**User need**: "Validate content safety and inspect agent budgets before publishing."

**Recommended skills**:

- `guardrail_check`
- `budget_status`
- `blackboard_status`

**What to look at**:

- Guardrail violations in the event stream.
- Budget tokens, API calls, and cost remaining.
- Blackboard entries for agent coordination.

**API payload**: `examples/user_payloads/guardrail_check.json`  
**API payload**: `examples/user_payloads/governance_status.json`

## Example 8: Multi-Agent Workflow

**User need**: "Have multiple agents collaborate on a task."

**Recommended skills**:

- `agent_workflow`

**Useful metadata**:

- `workflow_type`: `sequential` or `parallel`
- `agent_sequence`: ordered agent IDs
- `agents`: agent definitions with roles

**API payload**: `examples/user_payloads/multi_agent_workflow.json`

## Example 9: Storage Health Check

**User need**: "Check if decentralized storage is ready before uploading."

**Recommended skills**:

- `autonomi_status`

**API payload**: `examples/user_payloads/storage_status.json`

## Example 10: Formal Grammar Analysis

**User need**: "Analyze or verify a formal grammar specification."

**Recommended skills**:

- `alm_analyze`
- `alm_generate`
- `alm_verify`

**Useful metadata**:

- `grammar_spec`: BNF or EBNF grammar string
- `prefix`: token prefix for generation
- `count`: number of tokens to generate

**API payload**: `examples/user_payloads/formal_grammar_analysis.json`

## Example 11: STEM Compute

**User need**: "Run symbolic math or physics calculations."

**Recommended skills**:

- `math_compute`
- `physics_compute`

**Useful metadata for math**:

- `math_operation`: `solve`, `simplify`, `differentiate`, `integrate`, `evaluate`
- `math_expression`: expression string
- `math_variable`: variable name (default `x`)

**Useful metadata for physics**:

- `physics_operation`: `convert`, `transform`, `calculate`, `query`
- `physics_type`: `unit`, `coordinate`, `time`, `distance`, `energy`
- `physics_value`: value to process
- `physics_from_unit` / `physics_to_unit`: for conversions

**API payload**: `examples/user_payloads/math_solve.json`  
**API payload**: `examples/user_payloads/physics_unit_convert.json`

### STEM Visualizations & Simulations

**Quantum circuits**:

- `quantum_circuit_visualization` — 3D gate layout with Qiskit integration
- Metadata: `qubits` (default 4), `depth` (default 8), `custom_gates` array

**Molecular structures**:

- `molecular_visualization` — 3D atomic coordinates and bond topology
- Built-in molecules: `water`, `benzene`, `caffeine`, `protein` (with `residues`)

**Hardware emulation**:

- `riscv_sim` — RV32I emulator with assembler
- Metadata: `assembly` string, `memory_size`
- `verilator_sim` — Verilog lint and simulation readiness check
- `platformio` — Embedded project scaffolding

**Geometric topology**:

- `trefoil_simulation` — Quaternion trefoil knots on Clifford torus
- Metadata: `num_points` (default 256), `num_trefoils` (default 3), `rotation_speed`

**API payload**: `examples/user_payloads/trefoil_simulation.json`

## Example 12: Ecosystem Health Check

**User need**: "Check the status of all configured UOR ecosystem integrations."

**Recommended skills**:

- `uor_ecosystem_status`

**API payload**: `examples/user_payloads/ecosystem_status.json`

## Example 13: Visual Debugging Checklist

When a run does not look right:

1. **Open Timeline** and confirm the expected skills or recipes ran.
2. **Open Metrics** and check for slow or repeated skills.
3. **Open Dependency Graph** and inspect the hub node and disconnected groups.
4. **Export graph JSON** and confirm the graph has expected `nodes` and `edges`.
5. **Switch to JSON events** to inspect raw `recipe_start`, `skill_start`, `metrics`, and `orchestration_plan` events.

## Example 14: Which Workflow Should I Pick?

| Need | Start With | Add Later |
| --- | --- | --- |
| Understand a repo | `doc_ingest`, `dependency_map` | `sum_review` |
| Summarize docs | `doc_ingest`, `section_sum` | `ollama_generate` |
| Ask semantic questions | `graphrag_query` | `graphrag_index` first if needed |
| Build persistent knowledge | `graphrag_index` | `graphrag_query` |
| Inspect performance | Any streaming run | Metrics dashboard |
| Debug ordering | Recipes + streaming | Timeline JSON events |
| Store verifiable objects | UOR `/objects` | Lineage/workflow endpoints |
| Validate content safety | `guardrail_check` | `budget_status` |
| Multi-agent collaboration | `agent_workflow` | Configure `agents` metadata |
| Check storage readiness | `autonomi_status` | `autonomi_upload` |
| Analyze formal grammar | `alm_analyze` | `alm_generate` |
| Symbolic math | `math_compute` | `physics_compute` |
| Check integrations | `uor_ecosystem_status` | Individual ecosystem skills |

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
