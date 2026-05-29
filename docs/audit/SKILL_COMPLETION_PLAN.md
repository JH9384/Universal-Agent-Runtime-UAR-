# UAR Skill Completion Plan

## Goal
Convert the ~45 stub/placeholder skills into real implementations, prioritized by user value and implementation complexity.

---

## Phase 0: Quick Wins (1 day) — STEM + Visualizers

| Skill | Why | Approach |
|-------|-----|----------|
| `scipy_opt` | `scipy` is in requirements, real code can work now | Wrap `scipy.optimize`, `scipy.integrate`, `scipy.linalg` via `require_package` pattern. Return structured results. |
| `data_viz_3d` | numpy+matplotlib already loaded | Pure matplotlib 3D surface/wireframe. No `pyvista` needed for basic version. |
| `diff_eq_solve` | sympy is installed | Use SymPy `dsolve` for symbolic ODE solving. Fallback to numerical if scipy present. |

**Deliverables**: 3 real skills + tests. Remove from `stub_skills.py`.

---

## Phase 1: STEM Completion (1 week)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `quantum_circuit` | `qiskit` | Build simple circuits (Bell state, QFT), return gate counts + circuit diagrams as base64 images. |
| `chem_analysis` | `rdkit` | RDKit SMILES parsing, molecular weight, logP, basic descriptors. No conformer search needed for MVP. |
| `bio_compute` | `biopython` | DNA/RNA transcription/translation, sequence alignment via `PairwiseAligner`. |
| `relativity` | `einsteinpy` | Schwarzschild metric, geodesic calculations. Pure symbolic. |
| `cern_root` | `uproot` | Read ROOT files, extract TTree data as pandas DataFrames. |
| `quantum_ml` | `pennylane` | Variational quantum circuit, basic optimization loop. |

**Deliverables**: 6 real skills + tests each. Update `pyproject.toml` extras.

---

## Phase 2: Multi-Agent Fix (1 day) — Critical Honesty

**Options** (pick one):

1. **Rename** "Multi-Agent" group to "UAR Agent Patterns" — keep the code, stop the cosplay
2. **Integrate for real** — add `crewai` to base deps, wire `crewai.Agent` + `Crew` into `_perform_task`

If option 2:
- Install `crewai>=0.80` in base environment
- Create `uar/core/crewai_real.py` with actual CrewAI wrappers
- Keep `uar/core/crewai_integration.py` as fallback
- `crewai_task` checks `CREWAI_AVAILABLE`, delegates to real or fallback

**Deliverables**: No more theater. Skill either works with real CrewAI or is honest about being UAR-native.

---

## Phase 3: LLM AutoML (3 days)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `optuna_tune` | `optuna` | Objective function wrapper, study creation, best params output. |
| `flaml_auto` | `flaml` | AutoML.fit with timeout, return best model + metrics. |
| `pycaret_ml` | `pycaret` | Setup + compare_models + create_model pipeline. |

**Note**: These need sample data. Accept metadata pointing to CSV or use sklearn synthetic datasets.

---

## Phase 4: CV + ChromaDB (1 week)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `chromadb_store` | `chromadb` | Collection create, add documents, query with embedding. |
| `opencv_process` | `opencv-python` | Image resize, grayscale, edge detection, feature matching. Accept file path from metadata. |
| `video_analyze` | `opencv-python` + `moviepy` | Frame extraction, motion detection histogram. |
| `face_recognize` | `face-recognition` | Load image, find faces, encode, compare encodings. |
| `yolo_detect` | `ultralytics` | Load YOLOv8n, detect on image path, return boxes + labels. |

---

## Phase 5: Security + MLOps (1 week)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `security_audit` | `bandit` + `safety` | Run bandit on code path, return issues. Run safety on requirements. |
| `pentest_scan` | `python-nmap` | Nmap wrapper, parse XML output, return open ports. |
| `osint_recon` | `requests` + `shodan` | Domain WHOIS lookup, Shodan host search if key present. |
| `mlflow_track` | `mlflow` | Log params/metrics/artifact to local or remote MLflow. |
| `mlflow_deploy` | `mlflow` | Load model from registry, return deployment status. |
| `model_reg` | `mlflow` | Register model version, stage transition. |
| `kubeflow_pipe` | `kfp` | Create pipeline from Python func, compile to YAML. |

---

## Phase 6: Data Engineering (3 days)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `airflow_dag` | `apache-airflow` | Validate DAG file syntax, list tasks, return DAG structure. |
| `dbt_transform` | `dbt-core` | Run `dbt compile` on project path, return model list. |
| `spark_process` | `pyspark` | Create SparkSession, read CSV/Parquet, run SQL, return schema + sample. |
| `snowflake_etl` | `snowflake-connector-python` | Connect, execute query, return results as list of dicts. |

---

## Phase 7: Blockchain (2 days)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `solana_tx` | `solana` | Create keypair, check balance, send SOL to address. Testnet only. |
| `smart_contract` | `web3` | Deploy simple contract to local Anvil/Hardhat, return address. |
| `nft_mint` | `web3` | Mint ERC-721 to local testnet. |

**Note**: Blockchain skills should default to testnets. Never auto-use mainnet.

---

## Phase 8: Advanced RAG + Pipeline (1 week)

| Skill | Dependency | Approach |
|-------|-----------|----------|
| `llamaindex_rag` | `llama-index` | SimpleVectorIndex from documents, query engine. |
| `llamaindex_query` | `llama-index` | Query existing index with hybrid search. |
| `dagster_pipeline` | `dagster` | Define simple asset graph, materialize, return run ID. |
| `dagster_status` | `dagster` | Query Dagster instance for pipeline runs. |
| `flexible_graphrag` | `neo4j` + `rdflib` | In-memory graph builder with configurable backends. |

---

## Phase 9: UI Honesty Layer (1 day)

Add badges to `UARPanel.tsx`:

```typescript
const BADGES: Record<string, 'real' | 'stub' | 'cosplay'> = {
  crewai_task: 'cosplay',
  crewai_workflow: 'cosplay',
  optuna_tune: 'stub',
  // ... etc
}
```

Render `🟢`, `🟡`, `🔴` indicators next to skills. Stub skills disabled by default with tooltip: "Install X to enable".

---

## Appendix: Definition of "Real"

A skill is **real** when:

1. It performs the claimed computation or operation
2. It handles errors gracefully (not just `return {"status": "completed"}`)
3. It has unit/integration tests
4. It produces structured output usable by downstream skills
5. It does not just check if a package is installed and return a message

A skill is **cosplay** when:

1. It uses the name/branding of an external framework
2. It does not import or use that framework's code
3. It implements a similar concept with UAR-native code
4. It should be renamed or integrated for real
