import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'
import { SkillGuide } from './SkillGuide'
import styles from './UARPanel.module.css'

const MAX_EVENTS = 1000
const RECENT_KEY = 'uar.recentPaths'
const RECIPES_KEY = 'uar.recipes'
const RECENT_MAX = 8

// Improved ID generation with collision prevention
// Module-level counter (resets on page reload, which is acceptable for this use case)
let idCounter = 0
// Component instance ID to prevent cross-reload collisions with persisted IDs
const componentInstanceId = Math.random().toString(36).substring(2, 9)
const generateUniqueId = (existingIds?: Set<string>): string => {
  const generate = (): string => {
    try {
      return crypto.randomUUID()
    } catch {
      // Fallback: use timestamp + counter + random + component instance for better collision resistance
      const timestamp = Date.now().toString(36)
      const counter = (idCounter++).toString(36)
      const random = Math.random().toString(36).substring(2, 9)
      return `${timestamp}-${counter}-${random}-${componentInstanceId}`
    }
  }
  let id = generate()
  // Check for collisions if existingIds is provided
  if (existingIds) {
    let attempts = 0
    const maxAttempts = 100  // Increased from 10 to handle high-frequency scenarios
    while (existingIds.has(id) && attempts < maxAttempts) {
      id = generate()
      attempts++
    }
    if (attempts >= maxAttempts) {
      console.error('Failed to generate unique ID after 100 attempts - using fallback with timestamp')
      // Ultimate fallback: use full timestamp with nanosecond precision if available
      return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}-${componentInstanceId}`
    }
  }
  return id
}

// TypeScript interfaces for type safety
interface GraphNode {
  id?: string
  skill?: string
  type?: string
  [key: string]: any
}

interface GraphEdge {
  from?: string
  to?: string
  [key: string]: any
}

interface ExecutionOrderItem {
  id: string
  type: 'skill' | 'recipe'
  content: string
}

interface IngestedDocument {
  name: string
  path: string
  size?: number
  [key: string]: any
}

interface RejectionItem {
  name: string
  reason: string
}

interface ErrorResponse {
  message?: string
  error?: string
}

interface JobStatus {
  rejected?: RejectionItem[]
  [key: string]: any
}

interface RunRequestMetadata {
  graphrag_method?: string
  graphrag_query?: string
  ollama_model?: string
  autonomi_private_key?: string
  autonomi_network?: string
  autonomi_public?: boolean
  autonomi_address?: string
  [key: string]: any
}

const SKILL_GROUPS = [
  {
    name: 'Core UAR',
    icon: '⚙️',
    skills: [
      { id: 'doc_ingest',     label: 'doc_ingest',     desc: 'Read files from input_path (.md .txt .py .ts .json …)' },
      { id: 'doc_ingest_enhanced', label: 'doc_ingest_enhanced', desc: 'Advanced document ingestion with Unstructured & Docling (PDF, DOCX, images, tables)' },
      { id: 'dependency_map', label: 'dependency_map', desc: 'Build a dependency graph between artifacts' },
      { id: 'section_sum',    label: 'section_sum',    desc: 'Summarize document sections' },
      { id: 'sum_review',     label: 'sum_review',     desc: 'Final review of pipeline outputs' },
    ]
  },
  {
    name: 'AI / LLM',
    icon: '🧠',
    skills: [
      { id: 'ollama_generate', label: 'ollama_generate', desc: 'Send goal + ingested docs to local Ollama model (requires Ollama running)' },
      { id: 'openai_chat', label: 'openai_chat', desc: 'Chat with OpenAI GPT models (requires openai package + OPENAI_API_KEY)' },
      { id: 'openai_completion', label: 'openai_completion', desc: 'Text completion with OpenAI models (requires openai package + OPENAI_API_KEY)' },
      { id: 'openai_embedding', label: 'openai_embedding', desc: 'Generate embeddings for text (requires openai package + OPENAI_API_KEY)' },
      { id: 'lm_studio_chat', label: 'lm_studio_chat', desc: 'Chat with local LM Studio models (requires LM Studio running)' },
      { id: 'lm_studio_completion', label: 'lm_studio_completion', desc: 'Text completion with LM Studio (requires LM Studio running)' },
      { id: 'lm_studio_embedding', label: 'lm_studio_embedding', desc: 'Generate embeddings with LM Studio (requires LM Studio running)' },
      { id: 'anthropic_chat', label: 'anthropic_chat', desc: 'Chat with Claude models (requires anthropic package + ANTHROPIC_API_KEY)' },
      { id: 'anthropic_completion', label: 'anthropic_completion', desc: 'Text completion with Claude (requires anthropic package + ANTHROPIC_API_KEY)' },
      { id: 'anthropic_embedding', label: 'anthropic_embedding', desc: 'Generate embeddings with Claude (not currently supported by Anthropic API)' },
      { id: 'gemini_chat', label: 'gemini_chat', desc: 'Chat with Gemini models (requires google-generativeai package + GEMINI_API_KEY)' },
      { id: 'gemini_completion', label: 'gemini_completion', desc: 'Text completion with Gemini (requires google-generativeai package + GEMINI_API_KEY)' },
      { id: 'gemini_embedding', label: 'gemini_embedding', desc: 'Generate embeddings with Gemini (requires google-generativeai package + GEMINI_API_KEY)' },
      { id: 'mistral_chat', label: 'mistral_chat', desc: 'Chat with Mistral models (requires openai package + MISTRAL_API_KEY)' },
      { id: 'mistral_completion', label: 'mistral_completion', desc: 'Text completion with Mistral (requires openai package + MISTRAL_API_KEY)' },
      { id: 'mistral_embedding', label: 'mistral_embedding', desc: 'Generate embeddings with Mistral (requires openai package + MISTRAL_API_KEY)' },
      { id: 'groq_chat', label: 'groq_chat', desc: 'Ultra-fast chat with Groq (requires openai package + GROQ_API_KEY)' },
      { id: 'groq_completion', label: 'groq_completion', desc: 'Ultra-fast completion with Groq (requires openai package + GROQ_API_KEY)' },
      { id: 'huggingface_chat', label: 'huggingface_chat', desc: 'Chat with HF models (requires openai package + HF_API_KEY)' },
      { id: 'huggingface_completion', label: 'huggingface_completion', desc: 'Text completion with HF (requires openai package + HF_API_KEY)' },
      { id: 'huggingface_embedding', label: 'huggingface_embedding', desc: 'Generate embeddings with HF (requires openai package + HF_API_KEY)' },
      { id: 'together_chat', label: 'together_chat', desc: 'Chat with Together models (requires openai package + TOGETHER_API_KEY)' },
      { id: 'together_completion', label: 'together_completion', desc: 'Text completion with Together (requires openai package + TOGETHER_API_KEY)' },
      { id: 'together_embedding', label: 'together_embedding', desc: 'Generate embeddings with Together (requires openai package + TOGETHER_API_KEY)' },
      { id: 'optuna_tune', label: 'optuna_tune', desc: 'Hyperparameter optimization with Optuna - automated tuning for ML models (requires optuna)' },
      { id: 'autogluon_ml', label: 'autogluon_ml', desc: 'AutoML with AutoGluon - automated ML with ensemble methods (requires autogluon)' },
      { id: 'pycaret_ml', label: 'pycaret_ml', desc: 'Low-code ML with PyCaret - classification, regression, clustering (requires pycaret)' },
      { id: 'flaml_auto', label: 'flaml_auto', desc: 'AutoML with FLAML - efficient hyperparameter tuning (requires flaml)' },
      { id: 'chromadb_store', label: 'chromadb_store', desc: 'Vector database with ChromaDB - semantic search, embeddings storage (requires chromadb)' },
    ]
  },
  {
    name: 'Multi-Agent',
    icon: '🤖',
    skills: [
      { id: 'agent_workflow', label: 'agent_workflow', desc: 'Execute multi-agent workflows with Microsoft Agent Framework patterns (requires autogen)' },
      { id: 'crewai_task', label: 'crewai_task', desc: 'Execute role-based agent tasks with CrewAI patterns (requires crewai)' },
      { id: 'crewai_workflow', label: 'crewai_workflow', desc: 'Execute standard multi-agent workflows (research-analyze-write, code-review, data-analysis)' },
    ]
  },
  {
    name: 'Advanced RAG',
    icon: '📖',
    skills: [
      { id: 'llamaindex_rag', label: 'llamaindex_rag', desc: 'Advanced RAG with LlamaIndex - hierarchical chunking, hybrid search, knowledge graph (requires llama-index)' },
      { id: 'llamaindex_query', label: 'llamaindex_query', desc: 'Query LlamaIndex RAG system with multiple retrieval strategies (requires llama-index)' },
    ]
  },
  {
    name: 'Pipeline Orchestration',
    icon: '🔄',
    skills: [
      { id: 'dagster_pipeline', label: 'dagster_pipeline', desc: 'Execute Dagster pipelines with asset-based orchestration (requires dagster)' },
      { id: 'dagster_status', label: 'dagster_status', desc: 'Check Dagster pipeline and asset status (requires dagster)' },
    ]
  },
  {
    name: 'Governance',
    icon: '🛡️',
    skills: [
      { id: 'guardrail_check', label: 'guardrail_check', desc: 'Check guardrails for agent outputs - content safety, rate limits, budgets' },
      { id: 'budget_status', label: 'budget_status', desc: 'Check agent budget status - tokens, API calls, cost, time limits' },
      { id: 'blackboard_status', label: 'blackboard_status', desc: 'Check shared blackboard status for agent coordination' },
    ]
  },
  {
    name: 'GraphRAG',
    icon: '📚',
    skills: [
      { id: 'graphrag_init',   label: 'graphrag_init',   desc: 'Initialize GraphRAG workspace (one-time setup)' },
      { id: 'graphrag_index',  label: 'graphrag_index',  desc: 'Build a GraphRAG knowledge graph over input_path (slow; one-time)' },
      { id: 'graphrag_query',  label: 'graphrag_query',  desc: 'Query the GraphRAG index. Metadata: graphrag_method=local|global' },
      { id: 'flexible_graphrag', label: 'flexible_graphrag', desc: 'Flexible GraphRAG with multiple backends (Neo4j, Memgraph, RDF) and hybrid search' },
    ]
  },
  {
    name: 'Autonomi',
    icon: '☁️',
    skills: [
      { id: 'autonomi_upload',   label: 'autonomi_upload',   desc: 'Upload file/dir to Autonomi decentralized storage (requires autonomi package + wallet)' },
      { id: 'autonomi_download', label: 'autonomi_download', desc: 'Download a file from Autonomi by address (requires autonomi package)' },
      { id: 'autonomi_status',   label: 'autonomi_status',   desc: 'Check Autonomi client and wallet status' },
    ]
  },
  {
    name: 'ALM',
    icon: '🔤',
    skills: [
      { id: 'alm_analyze',      label: 'alm_analyze',      desc: 'Analyze formal grammar specifications (BNF, EBNF) with ALM (requires ALM service)' },
      { id: 'alm_generate',     label: 'alm_generate',     desc: 'Generate token sequences from a prefix using ALM (requires ALM service)' },
      { id: 'alm_verify',       label: 'alm_verify',       desc: 'Validate text against ALM grammar (requires ALM service)' },
    ]
  },
  {
    name: 'STEM',
    icon: '🔬',
    skills: [
      { id: 'math_compute',    label: 'math_compute',    desc: 'Symbolic math with SymPy: solve, differentiate, integrate, simplify (requires sympy)' },
      { id: 'cipher_ops',      label: 'cipher_ops',      desc: 'Cryptographic operations: encrypt, decrypt, hash, sign (requires pycryptodome)' },
      { id: 'physics_compute', label: 'physics_compute', desc: 'Physics & astronomy: unit conversion, coordinate transforms, cosmology (requires astropy)' },
      { id: 'diff_eq_solve',    label: 'diff_eq_solve',    desc: 'Differential equations with diffeqpy: ODE/PDE solvers, symbolic optimization (requires diffeqpy)' },
      { id: 'cern_root',       label: 'cern_root',       desc: 'CERN ROOT data analysis: particle physics, large datasets, statistical analysis (requires root-cern/pyroot)' },
      { id: 'scipy_opt',       label: 'scipy_opt',       desc: 'SciPy optimization: linear/nonlinear programming, integration, interpolation, eigenvalues (requires scipy)' },
      { id: 'quantum_circuit',  label: 'quantum_circuit',  desc: 'Quantum computing with Qiskit: build circuits, run on IBM Q, quantum algorithms (requires qiskit)' },
      { id: 'quantum_ml',      label: 'quantum_ml',      desc: 'Quantum ML with PennyLane: quantum neural networks, quantum chemistry (requires pennylane)' },
      { id: 'chem_analysis',   label: 'chem_analysis',   desc: 'Computational chemistry with RDKit: molecular analysis, conformers, chemical properties (requires rdkit)' },
      { id: 'bio_compute',     label: 'bio_compute',     desc: 'Bioinformatics with Biopython: DNA/RNA/protein analysis, sequence alignment (requires biopython)' },
      { id: 'relativity',      label: 'relativity',      desc: 'General relativity with EinsteinPy: spacetime metrics, geodesics, gravitational physics (requires einsteinpy)' },
      { id: 'data_viz_3d',     label: 'data_viz_3d',     desc: '3D visualization with PyVista: mesh analysis, VTK integration, scientific plotting (requires pyvista)' },
    ]
  },
  {
    name: 'Hardware / Embedded',
    icon: '⚡',
    skills: [
      { id: 'fpga_verify',     label: 'fpga_verify',     desc: 'FPGA verification with cocotb: Python testbenches for Verilog/SystemVerilog (requires cocotb)' },
      { id: 'verilog_parse',   label: 'verilog_parse',   desc: 'Verilog HDL processing with Pyverilog: parser, code analysis, code generation (requires pyverilog)' },
      { id: 'myhdl_design',    label: 'myhdl_design',    desc: 'Hardware design with MyHDL: Python to Verilog/VHDL conversion, simulation (requires myhdl)' },
      { id: 'riscv_sim',       label: 'riscv_sim',       desc: 'RISC-V simulation with riscemu: emulator for RISC-V assembly programs (requires riscemu)' },
      { id: 'riscv_cycle',     label: 'riscv_cycle',     desc: 'Cycle-accurate RISC-V with py-v: CPU simulator + RTL modeling (requires py-v)' },
      { id: 'verilator_sim',  label: 'verilator_sim',  desc: 'Verilog simulation with Verilator: high-speed SystemVerilog to C++/SystemC (requires verilator)' },
      { id: 'micropython',    label: 'micropython',    desc: 'MicroPython for embedded: ESP32/ESP8266, microcontroller programming (requires micropython)' },
      { id: 'platformio',     label: 'platformio',     desc: 'Embedded development with PlatformIO: Arduino, ESP32, STM32, CI/CD (requires platformio)' },
    ]
  },
  {
    name: 'Computer Vision',
    icon: '👁️',
    skills: [
      { id: 'yolo_detect',      label: 'yolo_detect',      desc: 'Object detection with YOLO - real-time detection, custom training (requires ultralytics)' },
      { id: 'opencv_process',   label: 'opencv_process',   desc: 'Image processing with OpenCV - filters, transforms, feature detection (requires opencv-python)' },
      { id: 'video_analyze',    label: 'video_analyze',    desc: 'Video analysis - motion detection, tracking, frame extraction (requires opencv-python)' },
      { id: 'face_recognize',   label: 'face_recognize',   desc: 'Face recognition - detection, identification, emotion analysis (requires face_recognition)' },
    ]
  },
  {
    name: 'Blockchain / Web3',
    icon: '🔗',
    skills: [
      { id: 'web3_eth',        label: 'web3_eth',        desc: 'Ethereum interaction with web3.py - smart contracts, transactions (requires web3)' },
      { id: 'solana_tx',       label: 'solana_tx',       desc: 'Solana transactions - SPL tokens, wallet management (requires solana-py)' },
      { id: 'smart_contract',  label: 'smart_contract',  desc: 'Smart contract deployment and interaction (requires web3, brownie)' },
      { id: 'nft_mint',        label: 'nft_mint',        desc: 'NFT minting and metadata management (requires web3, eth-account)' },
    ]
  },
  {
    name: 'MLOps',
    icon: '🚀',
    skills: [
      { id: 'mlflow_track',    label: 'mlflow_track',    desc: 'ML experiment tracking with MLflow - metrics, parameters, artifacts (requires mlflow)' },
      { id: 'mlflow_deploy',   label: 'mlflow_deploy',   desc: 'ML model deployment with MLflow - serving, batch inference (requires mlflow)' },
      { id: 'kubeflow_pipe',   label: 'kubeflow_pipe',   desc: 'ML pipelines with Kubeflow - workflow orchestration on K8s (requires kfp)' },
      { id: 'model_reg',       label: 'model_reg',       desc: 'Model registry management - versioning, staging, promotion (requires mlflow)' },
    ]
  },
  {
    name: 'Security',
    icon: '🔒',
    skills: [
      { id: 'pentest_scan',    label: 'pentest_scan',    desc: 'Penetration testing - vulnerability scanning, security assessment (requires nmap, python-nmap)' },
      { id: 'osint_recon',     label: 'osint_recon',     desc: 'OSINT reconnaissance - gather intelligence on targets (requires requests, shodan)' },
      { id: 'crypto_analyze',  label: 'crypto_analyze',  desc: 'Cryptographic analysis - hash cracking, encryption analysis (requires hashcat, pycryptodome)' },
      { id: 'security_audit',  label: 'security_audit',  desc: 'Security audit - code review, dependency vulnerabilities (requires bandit, safety)' },
    ]
  },
  {
    name: 'Data Engineering',
    icon: '📊',
    skills: [
      { id: 'airflow_dag',     label: 'airflow_dag',     desc: 'Workflow orchestration with Airflow - DAGs, scheduling, monitoring (requires apache-airflow)' },
      { id: 'dbt_transform',   label: 'dbt_transform',   desc: 'Data transformation with dbt - SQL models, testing, documentation (requires dbt-core)' },
      { id: 'snowflake_etl',   label: 'snowflake_etl',   desc: 'Snowflake ETL - data loading, warehousing, analytics (requires snowflake-connector-python)' },
      { id: 'spark_process',   label: 'spark_process',   desc: 'Big data processing with PySpark - ETL, analytics on large datasets (requires pyspark)' },
    ]
  },
]

const AVAILABLE_SKILLS = SKILL_GROUPS.flatMap(g => g.skills)

const GOAL_TEMPLATES = [
  'Summarize the project',
  'Document the architecture',
  'Build a dependency map of the codebase',
  'Review and identify inconsistencies in docs',
  'Index all source files for retrieval',
]

type Recipe = { id: string; label: string; skills: string[]; hint: string }
type UARError = { code?: string; message: string; requestId?: string; timestamp: number }
const RECIPES: Recipe[] = [
  { id: 'review',    label: '🦙 Ollama review',   skills: ['doc_ingest', 'ollama_generate'], hint: 'Quick LLM review of library docs' },
  { id: 'deps',      label: '🕸️ Dep map',          skills: ['doc_ingest', 'dependency_map', 'sum_review'], hint: 'Build a dependency graph' },
  { id: 'gr_index',  label: '📚 GraphRAG index',  skills: ['graphrag_index'], hint: 'Build the knowledge graph (slow, one-time)' },
  { id: 'gr_query',  label: '🔎 GraphRAG query',  skills: ['graphrag_query'], hint: 'Query an existing graph' },
  { id: 'gr_full',   label: '⚡ Full pipeline',    skills: ['graphrag_index', 'graphrag_query'], hint: 'Index then query (very slow)' },
  { id: 'auto_up',   label: '☁️ Autonomi upload',  skills: ['autonomi_upload'], hint: 'Upload current input_path to Autonomi' },
  { id: 'auto_down', label: '☁️ Autonomi download', skills: ['autonomi_download'], hint: 'Download from Autonomi address' },
  { id: 'auto_status', label: '☁️ Autonomi status',  skills: ['autonomi_status'], hint: 'Check Autonomi connectivity' },
]

type Preset = { name: string; path: string }
type BrowseEntry = { name: string; path: string; size: number; ext: string; is_dir: boolean }
type LibFile = { name: string; path: string; size: number; ext: string; mtime: number }
type BrowseResult = {
  path: string
  parent: string | null
  is_dir: boolean
  recursive: boolean
  file_count: number
  dir_count: number
  total_bytes: number
  truncated: boolean
  by_extension: Record<string, number>
  entries: BrowseEntry[]
}

function human(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// ============================================================
// FilePicker modal
// ============================================================
function FilePicker(props: {
  open: boolean
  initialPath: string
  projectRoot: string
  presets: Preset[]
  onClose: () => void
  onPick: (path: string) => void
}) {
  const { open, initialPath, projectRoot, presets, onClose, onPick } = props
  const [path, setPath] = useState(initialPath || projectRoot)
  const [data, setData] = useState<BrowseResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  const load = useCallback(async (p: string, recursive = false) => {
    setBusy(true); setErr(null)
    try {
      const r = await fetch(
        `/api/uar/docs/browse?path=${encodeURIComponent(p)}&limit=500&recursive=${recursive}`,
      )
      const j = await r.json()
      if (!r.ok) setErr(j.message || j.error || `HTTP ${r.status}`)
      else { setData(j); setPath(j.path || p) }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Browse failed')
    } finally { setBusy(false) }
  }, [])

  useEffect(() => {
    if (open) load(initialPath || projectRoot)
  }, [open, initialPath, projectRoot, load])

  if (!open) return null

  // Breadcrumbs
  const breadcrumbs: { label: string; path: string }[] = []
  if (data) {
    let acc = projectRoot
    breadcrumbs.push({ label: 'project_root', path: projectRoot })
    const rel = data.path.startsWith(projectRoot)
      ? data.path.slice(projectRoot.length).replace(/^\/+/, '')
      : data.path
    if (rel) {
      for (const part of rel.split('/').filter(Boolean)) {
        acc = `${acc}/${part}`
        breadcrumbs.push({ label: part, path: acc })
      }
    }
  }

  const filtered = (data?.entries || []).filter(
    (e) => !filter || e.name.toLowerCase().includes(filter.toLowerCase()),
  )

  return (
    <div onClick={onClose} className={styles.modalOverlay}>
      <div onClick={(e: React.MouseEvent) => e.stopPropagation()} className={styles.modalContent}>
        {/* Header */}
        <div className={styles.modalHeader}>
          <strong>Pick a folder or file</strong>
          <span className={styles.modalHeaderInfo}>(must be within PROJECT_ROOT)</span>
          <button onClick={onClose} className={styles.modalCloseButton}>✕</button>
        </div>

        {/* Presets row */}
        <div className={styles.presetsRow}>
          <span className={styles.quickLabel}>Quick:</span>
          <button onClick={() => load(projectRoot)} className={styles.presetButton}>/ root</button>
          {presets.map((p) => (
            <button key={p.path} onClick={() => load(p.path)} className={styles.presetButton}>
              {p.name}
            </button>
          ))}
        </div>

        {/* Breadcrumbs + nav */}
        <div className={styles.navRow}>
          <button
            onClick={() => data?.parent && load(data.parent)}
            disabled={!data?.parent || busy}
            title="Parent"
            className={styles.navButton}
          >⬆</button>
          <button onClick={() => data && load(data.path, true)} disabled={busy || !data?.is_dir} className={styles.navButton} title="Recursive listing">⤓</button>
          <button onClick={() => data && load(data.path)} disabled={busy} className={styles.navButton} title="Reload">⟳</button>
          <span className={styles.breadcrumbContainer}>
            {breadcrumbs.map((b, i) => (
              <span key={b.path}>
                <a onClick={() => load(b.path)} className={styles.breadcrumbLink}>{b.label}</a>
                {i < breadcrumbs.length - 1 && <span className={styles.breadcrumbSeparator}> / </span>}
              </span>
            ))}
          </span>
        </div>

        {/* Filter + manual path */}
        <div className={styles.filterRow}>
          <input
            placeholder="Filter (filename contains…)"
            value={filter}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFilter(e.target.value)}
            className={styles.filterInput}
          />
          <input
            placeholder="Or type a path and press Enter"
            value={path}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPath(e.target.value)}
            onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Enter') load(path) }}
            className={styles.pathInput}
          />
        </div>

        {/* Body */}
        <div className={styles.modalBody}>
          {err && <div className={styles.errorText}>Error: {err}</div>}
          {busy && <div className={styles.loadingText}>Loading…</div>}
          {!busy && !err && data && (
            <>
              <div className={styles.statsBar}>
                <strong>{data.dir_count}</strong> dirs · <strong>{data.file_count}</strong> files
                {data.total_bytes > 0 && <> · <strong>{human(data.total_bytes)}</strong></>}
                {data.truncated && <span className={styles.truncatedText}> · truncated</span>}
                {data.recursive && <span className={styles.recursiveText}> · recursive</span>}
                {Object.keys(data.by_extension).length > 0 && (
                  <span className={styles.extensionInfo}>
                    {Object.entries(data.by_extension).sort((a, b) => b[1] - a[1])
                      .slice(0, 8).map(([k, v]) => `${k}:${v}`).join('  ')}
                  </span>
                )}
              </div>
              <div className={styles.fileList}>
                {filtered.map((e) => (
                  <div
                    key={e.path}
                    onClick={() => e.is_dir ? load(e.path) : onPick(e.path)}
                    onDoubleClick={() => onPick(e.path)}
                    className={`${styles.fileItem} ${e.is_dir ? styles.fileItemDir : ''}`}
                    title={e.is_dir ? 'Click to open' : 'Click to select this file'}
                  >
                    <span>
                      {e.is_dir ? '📁 ' : '📄 '}
                      <span className={`${e.is_dir ? styles.fileIconDir : styles.fileIcon}`}>{e.name}</span>
                      {e.is_dir && '/'}
                    </span>
                    <span className={styles.fileSize}>{e.is_dir ? '' : human(e.size)}</span>
                  </div>
                ))}
                {filtered.length === 0 && <div className={styles.noEntries}>(no entries)</div>}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className={styles.modalFooter}>
          <span className={styles.selectedPath}>
            Selected: {data?.path || '(none)'}
          </span>
          <button onClick={onClose} className={styles.footerButton}>Cancel</button>
          <button
            onClick={() => data && onPick(data.path)}
            disabled={!data}
            className={styles.primaryButton}
          >
            Use this folder
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Main panel
// ============================================================
export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [inputPath, setInputPath] = useState('')
  const initialSkills = ['doc_ingest', 'dependency_map', 'sum_review']
  const [skillLastPositions, setSkillLastPositions] = useState<Record<string, number>>(() => {
    const positions: Record<string, number> = {}
    initialSkills.forEach((skill, idx) => positions[skill] = idx)
    return positions
  })
  const [recipes, setRecipes] = useState<Recipe[]>(() => {
    try {
      const saved = localStorage.getItem(RECIPES_KEY)
      return saved ? JSON.parse(saved) : RECIPES
    } catch (e) {
      console.warn('Failed to load recipes from localStorage:', e)
      return RECIPES
    }
  })
  const [recipeHistory, setRecipeHistory] = useState<Recipe[][]>([RECIPES])
  const [recipeHistoryIndex, setRecipeHistoryIndex] = useState(0)
  // Unified order combining both skills and recipes
  // Move ID generation inside useState to ensure fresh IDs on component mount
  const [unifiedOrder, setUnifiedOrder] = useState<{id: string; type: 'skill' | 'recipe'; content: string}[]>(() =>
    initialSkills.map(skill => ({ id: generateUniqueId(), type: 'skill' as const, content: skill }))
  )
  const [skillHistory, setSkillHistory] = useState<string[][]>([initialSkills])
  const [skillHistoryIndex, setSkillHistoryIndex] = useState(0)
  // Separate history for unified order to preserve instance IDs during undo/redo
  const [unifiedOrderHistory, setUnifiedOrderHistory] = useState<{id: string; type: 'skill' | 'recipe'; content: string}[][]>(() =>
    [initialSkills.map(skill => ({ id: generateUniqueId(), type: 'skill' as const, content: skill }))]
  )
  const [unifiedOrderHistoryIndex, setUnifiedOrderHistoryIndex] = useState(0)

  // selectedSkills is now derived from unifiedOrder to prevent state synchronization issues
  const selectedSkills = useMemo(() => {
    const recipeSkills = unifiedOrder
      .filter(i => i.type === 'recipe')
      .flatMap((item) => {
        const recipe = recipes.find((r) => r.id === item.content)
        return recipe ? recipe.skills : []
      })
    const manualSkills = unifiedOrder
      .filter(i => i.type === 'skill')
      .map(i => i.content)
    const combinedSkills = [...manualSkills]
    recipeSkills.forEach((skill) => {
      if (!combinedSkills.includes(skill)) {
        combinedSkills.push(skill)
      }
    })
    return combinedSkills
  }, [unifiedOrder, recipes])

  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isStopping, setIsStopping] = useState(false)
  const [error, setError] = useState<UARError | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [skillGuideOpen, setSkillGuideOpen] = useState(false)
  const [currentSkill, setCurrentSkill] = useState<string>('')
  const [startTime, setStartTime] = useState<number>(0)
  // Advanced overrides
  const [graphragMethod, setGraphragMethod] = useState<'local' | 'global'>('local')
  const [ollamaModel, setOllamaModel] = useState<string>('')
  // Autonomi overrides
  const [autonomiKey, setAutonomiKey] = useState<string>('')
  const [autonomiNetwork, setAutonomiNetwork] = useState<'testnet' | 'mainnet'>('testnet')
  const [autonomiPublic, setAutonomiPublic] = useState<boolean>(false)
  const [autonomiAddress, setAutonomiAddress] = useState<string>('')
  // Backend skills for validation consistency
  const [backendSkills, setBackendSkills] = useState<string[]>([])

  // Document management
  const [presets, setPresets] = useState<Preset[]>([])
  const [projectRoot, setProjectRoot] = useState<string>('')
  const [libraryPath, setLibraryPath] = useState<string>('')
  const [library, setLibrary] = useState<LibFile[]>([])
  const [libBusy, setLibBusy] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const tipsPopupRef = useRef<HTMLDivElement | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [tipsPopupOpen, setTipsPopupOpen] = useState(false)
  const [libraryPopupOpen, setLibraryPopupOpen] = useState(false)
  const [recipesPopupOpen, setRecipesPopupOpen] = useState(false)
  const [expandedTipSections, setExpandedTipSections] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    const sections = ['Documents', 'Goal', 'Skills', 'Run', 'Events', 'Graph', ...SKILL_GROUPS.map(g => g.name)]
    // Only expand key sections by default for better performance
    const keySections = ['Documents', 'Goal', 'Skills']
    sections.forEach(s => initial[s] = keySections.includes(s))
    return initial
  })
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    SKILL_GROUPS.forEach(g => initial[g.name] = false)
    return initial
  })
  const [recent, setRecent] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(RECENT_KEY)
      return saved ? JSON.parse(saved) : []
    } catch (e) {
      console.warn('Failed to load recent paths from localStorage:', e)
      return []
    }
  })

  // Save recipes to localStorage when they change
  useEffect(() => {
    try {
      localStorage.setItem(RECIPES_KEY, JSON.stringify(recipes))
    } catch (e) {
      // Handle localStorage quota exceeded errors gracefully
      if (e instanceof DOMException && (e.name === 'QuotaExceededError' || e.code === 22)) {
        console.error('localStorage quota exceeded - recipes not saved')
      } else {
        console.warn('Failed to save recipes to localStorage:', e)
      }
    }
  }, [recipes])

  const abortControllerRef = useRef<AbortController | null>(null)
  const eventCountRef = useRef(0)

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsRunning(false)
    setIsStopping(false)
    setCurrentSkill('')
    setStartTime(0)
  }, [])

  useEffect(() => cleanup, [])

  const refreshLibrary = useCallback(async () => {
    setLibBusy(true)
    try {
      const r = await fetch('/api/uar/docs/library')
      const j = await r.json()
      if (r.ok) {
        setLibrary(j.entries || [])
        setLibraryPath(j.library || '')
      }
    } catch { /* ignore */ }
    finally { setLibBusy(false) }
  }, [])

  useEffect(() => {
    fetch('/api/uar/docs/presets')
      .then((r) => r.json())
      .then((d) => {
        setPresets(d.presets || [])
        setProjectRoot(d.project_root || '')
        if (d.library) {
          setLibraryPath(d.library)
          // Default input_path to the library on first load
          setInputPath((cur) => cur || d.library)
        }
      })
      .catch(() => {})
    refreshLibrary()
    // Fetch backend skills for validation consistency
    fetch('/api/uar/skills')
      .then((r) => r.json())
      .then((d) => {
        setBackendSkills(d.skills || [])
      })
      .catch(() => {
        // Fallback to AVAILABLE_SKILLS if endpoint fails
        setBackendSkills(AVAILABLE_SKILLS.map(s => s.id))
      })
  }, [refreshLibrary])

  const uploadFiles = useCallback(async (fileList: FileList | File[]) => {
    const files = Array.from(fileList)
    if (files.length === 0) return
    setUploadMsg(`Uploading ${files.length} file(s)…`)
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f, f.name))
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60_000) // 60s safety
    try {
      const r = await fetch('/api/uar/docs/upload', {
        method: 'POST', body: fd, signal: ctrl.signal,
      })
      clearTimeout(timer)
      const j = await r.json()
      if (!r.ok) {
        setUploadMsg(`Upload failed: ${j.message || j.error || r.status}`)
      } else {
        const okN = (j.saved || []).length
        const badN = (j.rejected || []).length
        const rejNotes = (j.rejected || []).map((x: RejectionItem) => `${x.name} (${x.reason})`).join(', ')
        setUploadMsg(`Saved ${okN}${badN ? ` · rejected ${badN}: ${rejNotes}` : ''}`)
        await refreshLibrary()
        // If exactly one file uploaded, pre-select it
        if (okN === 1) setInputPath(j.saved[0].path)
        else if (okN > 0 && j.library) setInputPath(j.library)
      }
    } catch (e: unknown) {
      setUploadMsg(`Upload error: ${e instanceof Error ? e.message : 'unknown'}`)
    }
  }, [refreshLibrary])

  const deleteLibFile = async (name: string) => {
    if (!confirm(`Delete "${name}" from library?`)) return
    try {
      const r = await fetch(`/api/uar/docs/library?name=${encodeURIComponent(name)}`, { method: 'DELETE' })
      if (r.ok) refreshLibrary()
      else {
        const j = await r.json().catch(() => ({}))
        setUploadMsg(`Delete failed: ${j.message || r.status}`)
      }
    } catch (e: unknown) {
      setUploadMsg(`Delete error: ${e instanceof Error ? e.message : 'unknown'}`)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files)
  }, [uploadFiles])

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(true) }
  const onDragLeave = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(false) }

  // ESC closes picker and tips popup
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPickerOpen(false)
        setTipsPopupOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPickerOpen, setTipsPopupOpen])

  // Click outside to close tips popup
  useEffect(() => {
    if (!tipsPopupOpen) return

    const timeoutRef: { current: number | null } = { current: null }

    const handleClickOutside = (e: MouseEvent) => {
      // Check if click is outside the popup and not on a button that might trigger DOM updates
      if (tipsPopupRef.current && !tipsPopupRef.current.contains(e.target as Node)) {
        // Small delay to ensure any button click handlers have time to process
        timeoutRef.current = window.setTimeout(() => {
          setTipsPopupOpen(false)
        }, 0)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current)
      }
    }
  }, [tipsPopupOpen, setTipsPopupOpen])

  const pushRecent = (p: string) => {
    if (!p.trim()) return
    setRecent((prev) => {
      const next = [p, ...prev.filter((x) => x !== p)].slice(0, RECENT_MAX)
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(next))
      } catch (e) {
        console.warn('Failed to save recent paths to localStorage:', e)
      }
      return next
    })
  }

  const clearRecent = () => {
    setRecent([])
    try {
      localStorage.removeItem(RECENT_KEY)
    } catch (e) {
      console.warn('Failed to clear recent paths from localStorage:', e)
    }
  }

  const toggleSkill = (id: string) => {
    // Toggle skill: remove first instance if exists, otherwise add new instance
    setUnifiedOrder((prev) => {
      // Check if skill already exists in order
      const existingIndex = prev.findIndex(i => i.type === 'skill' && i.content === id)
      
      if (existingIndex >= 0) {
        // Remove the first instance of this skill
        const newOrder = [...prev]
        newOrder.splice(existingIndex, 1)
        // Update last positions for all skills after the removal point
        setSkillLastPositions((prevPositions) => {
          const newPositions = { ...prevPositions }
          for (let i = existingIndex; i < newOrder.length; i++) {
            if (newOrder[i].type === 'skill') {
              newPositions[newOrder[i].content] = i
            }
          }
          return newPositions
        })
        // selectedSkills is now derived from unifiedOrder, no need to set it
        const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
        setSkillHistory((history) => {
          const newHistory = [...history.slice(0, skillHistoryIndex + 1), newSkills]
          setSkillHistoryIndex((idx) => idx + 1)
          return newHistory
        })
        // Save unified order to history to preserve instance IDs
        setUnifiedOrderHistory((history) => {
          const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
          setUnifiedOrderHistoryIndex((idx) => idx + 1)
          return newHistory
        })
        return newOrder
      } else {
        // Add a new instance of the skill
        const existingIds = new Set(prev.map(i => i.id))
        const newInstance = {
          id: generateUniqueId(existingIds),
          type: 'skill' as const,
          content: id
        }
        const newOrder = [...prev]
        const lastPosition = skillLastPositions[id] ?? newOrder.length
        // Insert at the last known position, or at the end if no position exists
        const insertPosition = Math.min(lastPosition, newOrder.length)
        newOrder.splice(insertPosition, 0, newInstance)
        // Update last positions for all skills after the insertion point
        setSkillLastPositions((prevPositions) => {
          const newPositions = { ...prevPositions }
          for (let i = insertPosition; i < newOrder.length; i++) {
            if (newOrder[i].type === 'skill') {
              newPositions[newOrder[i].content] = i
            }
          }
          return newPositions
        })
        // selectedSkills is now derived from unifiedOrder, no need to set it
        const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
        setSkillHistory((history) => {
          const newHistory = [...history.slice(0, skillHistoryIndex + 1), newSkills]
          setSkillHistoryIndex((idx) => idx + 1)
          return newHistory
        })
        // Save unified order to history to preserve instance IDs
        setUnifiedOrderHistory((history) => {
          const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
          setUnifiedOrderHistoryIndex((idx) => idx + 1)
          return newHistory
        })
        return newOrder
      }
    })
  }

  const undoSkills = () => {
    setSkillHistoryIndex((prevIndex) => {
      if (prevIndex > 0 && skillHistory.length > 0) {
        const newIndex = prevIndex - 1
        // Ensure index is within bounds
        if (newIndex < 0 || newIndex >= skillHistory.length) {
          console.warn('Undo would cause skillHistoryIndex to go out of bounds')
          return prevIndex
        }
        // selectedSkills is now derived from unifiedOrder, no need to set it
        return newIndex
      }
      return prevIndex
    })
    setUnifiedOrderHistoryIndex((prevIndex) => {
      if (prevIndex > 0 && unifiedOrderHistory.length > 0) {
        const newIndex = prevIndex - 1
        // Ensure index is within bounds
        if (newIndex < 0 || newIndex >= unifiedOrderHistory.length) {
          console.warn('Undo would cause unifiedOrderHistoryIndex to go out of bounds')
          return prevIndex
        }
        const newOrder = unifiedOrderHistory[newIndex]
        setUnifiedOrder(newOrder)
        // Recalculate skillLastPositions from the restored order
        const newPositions: Record<string, number> = {}
        newOrder.forEach((item, index) => {
          if (item.type === 'skill') {
            newPositions[item.content] = index
          }
        })
        setSkillLastPositions(newPositions)
        return newIndex
      }
      return prevIndex
    })
  }

  const redoSkills = () => {
    setSkillHistoryIndex((prevIndex) => {
      if (prevIndex < skillHistory.length - 1 && skillHistory.length > 0) {
        const newIndex = prevIndex + 1
        // Ensure index is within bounds
        if (newIndex < 0 || newIndex >= skillHistory.length) {
          console.warn('Redo would cause skillHistoryIndex to go out of bounds')
          return prevIndex
        }
        // selectedSkills is now derived from unifiedOrder, no need to set it
        return newIndex
      }
      return prevIndex
    })
    setUnifiedOrderHistoryIndex((prevIndex) => {
      if (prevIndex < unifiedOrderHistory.length - 1 && unifiedOrderHistory.length > 0) {
        const newIndex = prevIndex + 1
        // Ensure index is within bounds
        if (newIndex < 0 || newIndex >= unifiedOrderHistory.length) {
          console.warn('Redo would cause unifiedOrderHistoryIndex to go out of bounds')
          return prevIndex
        }
        const newOrder = unifiedOrderHistory[newIndex]
        setUnifiedOrder(newOrder)
        // Recalculate skillLastPositions from the restored order
        const newPositions: Record<string, number> = {}
        newOrder.forEach((item, index) => {
          if (item.type === 'skill') {
            newPositions[item.content] = index
          }
        })
        setSkillLastPositions(newPositions)
        return newIndex
      }
      return prevIndex
    })
  }

  const undoRecipes = () => {
    setRecipeHistoryIndex((prevIndex) => {
      if (prevIndex > 0 && recipeHistory.length > 0) {
        const newIndex = prevIndex - 1
        setRecipes(recipeHistory[newIndex])
        return newIndex
      }
      return prevIndex
    })
  }

  const redoRecipes = () => {
    setRecipeHistoryIndex((prevIndex) => {
      if (prevIndex < recipeHistory.length - 1 && recipeHistory.length > 0) {
        const newIndex = prevIndex + 1
        setRecipes(recipeHistory[newIndex])
        return newIndex
      }
      return prevIndex
    })
  }

  const toggleGroup = (name: string) => {
    setCollapsedGroups(prev => ({ ...prev, [name]: !prev[name] }))
  }

  const toggleTipSection = (name: string) => {
    setExpandedTipSections(prev => ({ ...prev, [name]: !prev[name] }))
  }

  const toggleAllGroups = (expand: boolean) => {
    const newState: Record<string, boolean> = {}
    SKILL_GROUPS.forEach(g => newState[g.name] = !expand)
    setCollapsedGroups(newState)
  }

  const onPick = (p: string) => {
    setInputPath(p)
    pushRecent(p)
    setPickerOpen(false)
  }

  const copyPath = async () => {
    try {
      await navigator.clipboard.writeText(inputPath)
    } catch {}
  }

  const runStream = useCallback(async () => {
    setEvents([]); setGraph(null); setError(null)
    setIsRunning(true)
    eventCountRef.current = 0
    abortControllerRef.current = new AbortController()

    // Validate inputs before sending request
    if (!goal.trim()) {
      setError({ message: 'Goal is required', timestamp: Date.now() })
      setIsRunning(false)
      return
    }
    if (unifiedOrder.length === 0) {
      setError({ message: 'At least one skill or recipe must be selected', timestamp: Date.now() })
      setIsRunning(false)
      return
    }

    // Send unified order as execution_order to support nested recipe execution
    const executionOrder = unifiedOrder.map(item => ({
      type: item.type,
      content: item.content,
      id: item.id
    }))

    // Validate execution_order structure comprehensively
    // Use backendSkills for validation consistency with backend registry
    const validSkills = new Set(backendSkills.length > 0 ? backendSkills : AVAILABLE_SKILLS.map(s => s.id))
    const validRecipes = new Set(recipes.map(r => r.id))
    const ids = new Set<string>()
    
    if (!Array.isArray(executionOrder)) {
      setError({ message: 'Execution order must be an array', timestamp: Date.now() })
      setIsRunning(false)
      return
    }
    
    for (const item of executionOrder) {
      // Check required fields
      if (!item.type || !item.content || !item.id) {
        setError({ message: 'Each execution order item must have type, content, and id', timestamp: Date.now() })
        setIsRunning(false)
        return
      }
      
      // Check type is valid
      if (!['skill', 'recipe'].includes(item.type)) {
        setError({ message: `Invalid type "${item.type}" in execution order. Must be "skill" or "recipe"`, timestamp: Date.now() })
        setIsRunning(false)
        return
      }
      
      // Check for duplicate IDs
      if (ids.has(item.id)) {
        setError({ message: `Duplicate ID "${item.id}" in execution order`, timestamp: Date.now() })
        setIsRunning(false)
        return
      }
      ids.add(item.id)
      
      // Validate content based on type
      if (item.type === 'skill' && !validSkills.has(item.content)) {
        setError({ message: `Invalid skill ID "${item.content}" in execution order`, timestamp: Date.now() })
        setIsRunning(false)
        return
      }
      
      if (item.type === 'recipe' && !validRecipes.has(item.content)) {
        setError({ message: `Invalid recipe ID "${item.content}" in execution order`, timestamp: Date.now() })
        setIsRunning(false)
        return
      }
    }

    // Derive skills directly from unifiedOrder to ensure consistency with execution_order
    const currentSkills = unifiedOrder
      .filter(i => i.type === 'skill')
      .map(i => i.content)
    const recipeSkills = unifiedOrder
      .filter(i => i.type === 'recipe')
      .flatMap((item) => {
        const recipe = recipes.find((r) => r.id === item.content)
        return recipe ? recipe.skills : []
      })
    const allSkills = [...new Set([...currentSkills, ...recipeSkills])]

    const body: { goal: string; skills: string[]; input_path?: string; metadata?: RunRequestMetadata; execution_order?: any[] } = { 
      goal, 
      skills: allSkills,
      execution_order: executionOrder
    }
    if (inputPath.trim()) { body.input_path = inputPath.trim(); pushRecent(inputPath.trim()) }
    
    // Check metadata against unifiedOrder to support recipe-specific metadata
    const allRecipes = unifiedOrder.filter(i => i.type === 'recipe').map(i => i.content)
    
    const meta: RunRequestMetadata = {}
    if (allSkills.includes('graphrag_query') || allRecipes.some(r => r === 'gr_query' || r === 'gr_full')) {
      meta.graphrag_method = graphragMethod
      meta.graphrag_query = goal
    }
    if (ollamaModel.trim() && (allSkills.includes('ollama_generate') || allRecipes.some(r => r === 'review'))) {
      meta.ollama_model = ollamaModel.trim()
    }
    if (allSkills.includes('autonomi_upload') || allSkills.includes('autonomi_download') || allSkills.includes('autonomi_status')) {
      if (autonomiKey.trim()) meta.autonomi_private_key = autonomiKey.trim()
      meta.autonomi_network = autonomiNetwork
      if (allSkills.includes('autonomi_upload')) {
        meta.autonomi_public = autonomiPublic
      }
      if (allSkills.includes('autonomi_download') && autonomiAddress.trim()) {
        meta.autonomi_address = autonomiAddress.trim()
      }
    }
    if (Object.keys(meta).length) body.metadata = meta

    // Add timeout to abort controller
    const timeoutId = setTimeout(() => {
      abortControllerRef.current?.abort()
      setError({ message: 'Request timeout - server did not respond in time', timestamp: Date.now() })
      setIsRunning(false)
    }, 300000) // 5 minute timeout

    try {
      setCurrentSkill(selectedSkills[0] || 'Starting')
      setStartTime(Date.now())
      const res = await fetch('/api/uar/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      })
      // Clear timeout immediately after fetch completes to prevent race condition
      clearTimeout(timeoutId)
      
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${res.statusText}${text ? ` — ${text}` : ''}`)
      }
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body reader available')

      let buffer = ''
      let lastEventTime = Date.now()
      const HEARTBEAT_INTERVAL = 30000 // 30 seconds
      const HEARTBEAT_ABORT_THRESHOLD = 2 // Abort after 2 missed heartbeats (60 seconds)
      let missedHeartbeats = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (abortControllerRef.current?.signal.aborted) break

        // Check for heartbeat/timeout
        const now = Date.now()
        if (now - lastEventTime > HEARTBEAT_INTERVAL) {
          missedHeartbeats++
          console.warn(`No events received for ${HEARTBEAT_INTERVAL / 1000}s (missed heartbeat ${missedHeartbeats}/${HEARTBEAT_ABORT_THRESHOLD})`)
          if (missedHeartbeats >= HEARTBEAT_ABORT_THRESHOLD) {
            abortControllerRef.current?.abort()
            setError({ message: `Connection stalled - no events received for ${HEARTBEAT_INTERVAL * HEARTBEAT_ABORT_THRESHOLD / 1000}s`, timestamp: Date.now() })
            break
          }
        } else {
          missedHeartbeats = 0
        }
        lastEventTime = now
        
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data:')) continue
            try {
              const json = JSON.parse(line.replace('data: ', ''))
              // Check event limit before processing to avoid processing events beyond limit
              if (eventCountRef.current >= MAX_EVENTS) {
                abortControllerRef.current?.abort()
                setError({ message: `Event limit reached (${MAX_EVENTS}).`, timestamp: Date.now() })
                setIsRunning(false)
                break
              }
              setEvents((prev) => {
                const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                eventCountRef.current++
                return [...next, json]
              })
              if (json.type === 'skill_start' && json.skill) setCurrentSkill(json.skill)
              if (json.type === 'skill_complete' && json.skill) setCurrentSkill(`Completed: ${json.skill}`)
              if (json.type === 'orchestration_plan' && json.payload?.graph) setGraph(json.payload.graph)
              if (json.run?.final_context?.dependency_map) setGraph(json.run.final_context.dependency_map)
              if (json.type === 'error' && json.error) setError({ message: json.error, timestamp: Date.now() })
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError, 'Data:', line)
              setError({ message: 'Failed to parse server response', timestamp: Date.now() })
            }
          }
          // Break outer loop if limit reached
          if (eventCountRef.current >= MAX_EVENTS) break
        }
      }
    } catch (err) {
      clearTimeout(timeoutId)
      if (err instanceof Error && err.name === 'AbortError') return
      setError({ message: err instanceof Error ? err.message : 'Unknown error occurred', timestamp: Date.now() })
    } finally {
      clearTimeout(timeoutId)
      setIsRunning(false)
      if (!abortControllerRef.current?.signal.aborted) {
        abortControllerRef.current = null
      }
    }
  }, [goal, inputPath, selectedSkills, unifiedOrder, graphragMethod, ollamaModel, autonomiKey, autonomiNetwork, autonomiPublic, autonomiAddress, pushRecent])

  const stopStream = useCallback(() => {
    setIsStopping(true)
    cleanup()
  }, [cleanup])

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] }
    const nodeIndex = new Map<string, string>()
    const nodes = (graph.nodes || []).map((n: GraphNode, i: number) => {
      const nodeId = n.id || n.skill || String(i)
      nodeIndex.set(nodeId, String(i))
      return {
        id: String(i),
        data: { label: n.skill || String(nodeId).split('/').pop(), type: n.type || 'skill' },
        position: { x: (i % 5) * 180, y: Math.floor(i / 5) * 120 },
      }
    })
    const edges = (graph.edges || [])
      .map((e: GraphEdge, i: number) => {
        const source = e.from ? nodeIndex.get(e.from) : undefined
        const target = e.to ? nodeIndex.get(e.to) : undefined
        if (source === undefined || target === undefined) return null
        return { id: String(i), source, target }
      })
      .filter(Boolean)
    return { nodes, edges }
  }, [graph])

  const clearEvents = useCallback(() => { setEvents([]); setError(null) }, [])

  const ingested = useMemo(() => {
    const last = [...events].reverse().find(
      (e) => e?.type === 'skill_complete' && e?.skill === 'doc_ingest'
    )
    return last?.payload?.result || null
  }, [events])

  const ollama = useMemo(() => {
    const last = [...events].reverse().find(
      (e) => e?.type === 'skill_complete' && e?.skill === 'ollama_generate'
    )
    return last?.payload?.result || null
  }, [events])

  const canRun = !isRunning && !isStopping && goal.trim().length > 0 && selectedSkills.length > 0

  const chip = (active: boolean, disabled = false): string => {
    const base = styles.chip
    if (active) return `${base} ${styles.chipActive}`
    if (disabled) return `${base} ${styles.chipDisabled}`
    return base
  }

  return (
    <div className={styles.container}>
      <FilePicker
        open={pickerOpen}
        initialPath={inputPath || libraryPath || projectRoot}
        projectRoot={projectRoot}
        presets={presets}
        onClose={() => setPickerOpen(false)}
        onPick={onPick}
      />

      <div className={styles.header}>
        <h3 className={styles.headerTitle}>🤖 Universal Agent Runtime (UAR)</h3>
        <button
          onClick={() => setShowHelp(!showHelp)}
          className={styles.skillGuideButton}
          title="Toggle quick start tips"
        >
          💡
        </button>
        <button
          onClick={() => setSkillGuideOpen(true)}
          className={styles.skillGuideButton}
          title="View detailed skill documentation"
        >
          📘
        </button>
        <span className={styles.projectRoot}>UOR Support</span>
      </div>

      {showHelp && (
        <div className={styles.helpBox}>
          <div className={styles.helpSection}>
            <strong>Quick Start:</strong>
            <ul className={styles.helpList}>
              <li>1. <strong>Select documents</strong> from the library or upload files</li>
              <li>2. <strong>Set a goal</strong> describing what you want to accomplish</li>
              <li>3. <strong>Choose skills</strong> to apply (use recipes for quick workflows)</li>
              <li>4. <strong>Run</strong> and monitor the execution in real-time</li>
            </ul>
          </div>
          <div className={styles.helpSection}>
            <strong>Pro Tips:</strong>
            <ul className={styles.helpList}>
              <li>Use <strong>Recipes</strong> for common workflows</li>
              <li><strong>doc_ingest</strong> reads files from your input_path</li>
              <li>Skills execute in the order shown</li>
              <li>Hover over skills for descriptions</li>
            </ul>
          </div>
        </div>
      )}

      {error && (
        <div className={styles.errorBox}>
          <strong>Error:</strong> {error.message}
          {error.code && <span className={styles.errorCode}>[{error.code}]</span>}
          {error.requestId && <span className={styles.errorCode}>req: {error.requestId}</span>}
          <button onClick={() => setError(null)} className={styles.dismissButton}>Dismiss</button>
          <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(error, null, 2)).catch(() => {}) }} className={styles.copyButton}>Copy</button>
        </div>
      )}

      {/* DOCUMENTS */}
      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong className={styles.sectionTitle} title="Manage documents, upload files, and select input paths">Documents</strong>
          <span className={styles.sectionInfo}>
            library: {libraryPath}
          </span>
          <button
            onClick={() => setTipsPopupOpen(true)}
            className={styles.skillGuideButton}
            title="View tips"
          >
            💡
          </button>
          <button
            onClick={() => setPickerOpen(true)}
            disabled={isRunning}
            className={styles.pickButton}
            title="Open file picker"
          >📂 Pick…</button>
        </div>

        <div className={styles.sectionWithTips}>
          <div className={styles.sectionContent}>
            {/* Drop zone */}
            <div
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`${styles.dropZone} ${dragActive ? styles.dropZoneActive : ''}`}
            >
              <div className={styles.dropZoneIcon}>{dragActive ? '⬇️' : '📥'}</div>
              <div className={styles.dropZoneText}>
                {dragActive ? 'Drop here to add to library' : 'Drop files here, or click to choose'}
              </div>
              <div className={styles.dropZoneSubtext}>
                PDFs · DOCX · XLSX · IPYNB · Parquet · Markdown · Code · Data · max 50MB each
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                aria-label="Upload files to library"
                className={styles.hiddenInput}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  if (e.target.files?.length) uploadFiles(e.target.files)
                  e.target.value = ''
                }}
              />
            </div>
            {uploadMsg && <div className={styles.uploadMessage}>{uploadMsg}</div>}

            {/* Library list */}
            <div className={styles.presetsContainer}>
              <div className={styles.label}>
                📚 Library ({library.length}{libBusy && ' · refreshing…'})
                <button onClick={refreshLibrary} className={styles.refreshButton} title="Refresh library list">↻</button>
                {libraryPath && (
                  <button onClick={() => onPick(libraryPath)} className={styles.useAllButton} title="Use whole library as input_path">
                    use all
                  </button>
                )}
              </div>
              {library.length === 0 ? (
                <div className={styles.emptyLibrary}>(empty — drop files above)</div>
              ) : (
                <div className={styles.libraryList}>
                  {library.map((f) => (
                    <div key={f.path}
                      className={`${styles.libraryItem} ${inputPath === f.path ? styles.libraryItemSelected : ''}`}
                    >
                      <span className={styles.libraryItemName} onClick={() => onPick(f.path)} title={f.path}>
                        📄 {f.name}
                      </span>
                      <span className={styles.libraryItemSize}>{human(f.size)}</span>
                      <button onClick={() => deleteLibFile(f.name)} disabled={isRunning} className={styles.deleteButton} title="Delete">✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className={styles.presetsContainer}>
              <div className={styles.label} title="Quick access to pre-configured project directories">Presets</div>
              {presets.length === 0 && <span className={styles.loadingText}>(loading…)</span>}
              {presets.map((p) => (
                <button key={p.path} disabled={isRunning} onClick={() => onPick(p.path)} className={chip(inputPath === p.path, isRunning)} title={p.path}>
                  {p.name}
                </button>
              ))}
            </div>

            {recent.length > 0 && (
              <div className={styles.recentContainer}>
                <div className={styles.label} title="Recently used paths for quick access">
                  Recent
                  <button onClick={clearRecent} className={styles.clearButton} title="Clear recent paths history">clear</button>
                </div>
                {recent.map((p) => (
                  <button key={p} disabled={isRunning} onClick={() => onPick(p)} className={chip(inputPath === p, isRunning)} title={p}>
                    {p.length > 40 ? '…' + p.slice(-40) : p}
                  </button>
                ))}
              </div>
            )}

            <div>
              <label className={styles.label} title="Specify which files or folder to process">input_path</label>
              <div className={styles.inputGroup}>
                <input
                  value={inputPath}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInputPath(e.target.value)}
                  placeholder="(none — doc_ingest will warn)"
                  disabled={isRunning}
                  className={styles.input}
                />
                <button onClick={copyPath} disabled={!inputPath} className={styles.iconButton} title="Copy path to clipboard">📋</button>
                <button onClick={() => setInputPath('')} disabled={!inputPath || isRunning} className={styles.iconButton} title="Clear input path">✕</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* GOAL + SKILLS */}
      <div className={styles.box}>
        <div className={styles.marginBottom12}>
          <label className={styles.label} title="Describe what you want to accomplish - guides AI processing">
            Goal
            <button
              onClick={() => setTipsPopupOpen(true)}
              className={styles.skillGuideButton}
              title="View tips"
            >
              💡
            </button>
          </label>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <input
                value={goal}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGoal(e.target.value)}
                placeholder="What do you want to accomplish?"
                disabled={isRunning}
                className={`${styles.input} ${styles.widthFull}`}
              />
              <datalist id="goal-templates">
                {GOAL_TEMPLATES.map((g) => <option key={g} value={g} />)}
              </datalist>
              <div className={styles.marginTop4}>
                {GOAL_TEMPLATES.map((g) => (
                  <button key={g} onClick={() => setGoal(g)} disabled={isRunning} className={`${chip(goal === g, isRunning)} ${styles.smallButton}`} title={g}>
                    {g.length > 30 ? g.slice(0, 30) + '…' : g}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <label className={styles.label} title="Select skills to execute in sequence">
            Skills
            <button
              onClick={() => setTipsPopupOpen(true)}
              className={styles.skillGuideButton}
              title="View tips"
            >
              💡
            </button>
            <button onClick={() => toggleAllGroups(false)} className={styles.collapseAllButton} disabled={isRunning} title="Collapse all">
              ▼
            </button>
            <button onClick={() => toggleAllGroups(true)} className={styles.collapseAllButton} disabled={isRunning} title="Expand all">
              ▲
            </button>
            <button onClick={() => {
              setUnifiedOrder((prev) => prev.filter(i => i.type === 'skill'))
              // selectedSkills is now derived from unifiedOrder, no need to set it
              setSkillHistory((history) => [...history.slice(0, skillHistoryIndex + 1), []])
              setSkillHistoryIndex((prev) => prev + 1)
              // Also clear unified order history
              setUnifiedOrderHistory((history) => [...history.slice(0, unifiedOrderHistoryIndex + 1), []])
              setUnifiedOrderHistoryIndex((prev) => prev + 1)
              // Reset skill last positions
              setSkillLastPositions({})
            }} className={styles.collapseAllButton} disabled={isRunning} title="Clear all selected skills">
              ✕
            </button>
            <button onClick={undoSkills} className={styles.collapseAllButton} disabled={isRunning || skillHistoryIndex === 0} title="Undo">
              ↶
            </button>
            <button onClick={redoSkills} className={styles.collapseAllButton} disabled={isRunning || skillHistoryIndex === skillHistory.length - 1} title="Redo">
              ↷
            </button>
          </label>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.skillsContainer}>
                {SKILL_GROUPS.map((group) => {
                  const isCollapsed = collapsedGroups[group.name]
                  return (
                    <div key={group.name} className={styles.skillGroup}>
                      <div className={styles.skillGroupHeader} onClick={() => toggleGroup(group.name)} title={`Click to ${isCollapsed ? 'expand' : 'collapse'} ${group.name} skills`}>
                        <span className={styles.skillGroupIcon}>{group.icon}</span>
                        <span className={styles.skillGroupName}>{group.name}</span>
                        <span className={styles.collapseIcon}>{isCollapsed ? '▶' : '▼'}</span>
                      </div>
                      {!isCollapsed && (
                        <div className={styles.skillGroupSkills}>
                          {group.skills.map((s) => (
                            <button key={s.id} onClick={() => toggleSkill(s.id)} disabled={isRunning} title={s.desc} className={chip(unifiedOrder.some(i => i.type === 'skill' && i.content === s.id), isRunning)}>
                              {unifiedOrder.filter(i => i.type === 'skill' && i.content === s.id).length > 0 ? `✓ (${unifiedOrder.filter(i => i.type === 'skill' && i.content === s.id).length}) ` : ''}{s.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className={styles.orderText} title="Skills execute in this order">
                <span>Order:</span>
                {unifiedOrder.length === 0 ? (
                  <span>(none)</span>
                ) : (
                  <div className={styles.orderChips}>
                    {unifiedOrder.map((item, index) => {
                      const hash = item.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
                      const colorClass = `color-${hash % 10}` as `color-${0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9}`
                      const label = item.type === 'skill' ? item.content : recipes.find(r => r.id === item.content)?.label || item.content
                      return (
                        <div
                          key={item.id}
                          className={`${styles.orderChip} ${styles[colorClass]}`}
                          draggable={!isRunning}
                          onDragStart={(e) => {
                            e.dataTransfer.setData('text/plain', String(index))
                            e.dataTransfer.effectAllowed = 'move'
                          }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault()
                            const fromIndex = parseInt(e.dataTransfer.getData('text/plain'))
                            const toIndex = index
                            if (fromIndex !== toIndex) {
                              setUnifiedOrder((prev) => {
                                const newOrder = [...prev]
                                const [moved] = newOrder.splice(fromIndex, 1)
                                newOrder.splice(toIndex, 0, moved)
                                // Update skillLastPositions for skills
                                setSkillLastPositions((prevPositions) => {
                                  const newPositions = { ...prevPositions }
                                  const minIndex = Math.min(fromIndex, toIndex)
                                  const maxIndex = Math.max(fromIndex, toIndex)
                                  for (let i = minIndex; i <= maxIndex; i++) {
                                    if (newOrder[i].type === 'skill') {
                                      newPositions[newOrder[i].content] = i
                                    }
                                  }
                                  return newPositions
                                })
                                // selectedSkills is now derived from unifiedOrder, no need to set it
                                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                                setSkillHistory((history) => {
                                  const newHistory = [...history.slice(0, skillHistoryIndex + 1), newSkills]
                                  setSkillHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                // Save unified order to history to preserve instance IDs
                                setUnifiedOrderHistory((history) => {
                                  const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
                                  setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                return newOrder
                              })
                            }
                          }}
                        >
                          {item.type === 'recipe' ? '🍳 ' : ''}{label}
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setUnifiedOrder((prev) => {
                                const newOrder = [...prev]
                                const existingIds = new Set(prev.map(i => i.id))
                                const newInstance = {
                                  id: generateUniqueId(existingIds),
                                  type: item.type,
                                  content: item.content
                                }
                                newOrder.splice(index + 1, 0, newInstance)
                                // Update skillLastPositions for skills
                                setSkillLastPositions((prevPositions) => {
                                  const newPositions = { ...prevPositions }
                                  for (let i = index + 1; i < newOrder.length; i++) {
                                    if (newOrder[i].type === 'skill') {
                                      newPositions[newOrder[i].content] = i
                                    }
                                  }
                                  return newPositions
                                })
                                // selectedSkills is now derived from unifiedOrder, no need to set it
                                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                                setSkillHistory((history) => {
                                  const newHistory = [...history.slice(0, skillHistoryIndex + 1), newSkills]
                                  setSkillHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                // Save unified order to history to preserve instance IDs
                                setUnifiedOrderHistory((history) => {
                                  const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
                                  setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                return newOrder
                              })
                            }}
                            className={styles.orderChipAction}
                            disabled={isRunning}
                            title={`Duplicate ${label}`}
                          >
                            +
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setUnifiedOrder((prev) => {
                                const newOrder = prev.filter((_, i) => i !== index)
                                // Update skillLastPositions for skills
                                setSkillLastPositions((prevPositions) => {
                                  const newPositions = { ...prevPositions }
                                  for (let i = index; i < newOrder.length; i++) {
                                    if (newOrder[i].type === 'skill') {
                                      newPositions[newOrder[i].content] = i
                                    }
                                  }
                                  return newPositions
                                })
                                // selectedSkills is now derived from unifiedOrder, no need to set it
                                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                                setSkillHistory((history) => {
                                  const newHistory = [...history.slice(0, skillHistoryIndex + 1), newSkills]
                                  setSkillHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                // Save unified order to history to preserve instance IDs
                                setUnifiedOrderHistory((history) => {
                                  const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
                                  setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                return newOrder
                              })
                            }}
                            className={styles.orderChipAction}
                            disabled={isRunning}
                            title={`Remove ${label}`}
                          >
                            ✕
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Recipes */}
              <div className={styles.presetsContainer}>
                <label className={styles.label} title="Pre-configured skill combinations for common workflows">
                  Recipes
                  <a
                    onClick={() => setRecipesPopupOpen(true)}
                    className={styles.libraryLink}
                    title="View recipes library"
                  >
                    📚
                  </a>
                  <button onClick={undoRecipes} className={styles.collapseAllButton} disabled={isRunning || recipeHistoryIndex === 0} title="Undo">
                    ↶
                  </button>
                  <button onClick={redoRecipes} className={styles.collapseAllButton} disabled={isRunning || recipeHistoryIndex === recipeHistory.length - 1} title="Redo">
                    ↷
                  </button>
                </label>
                <div className={styles.recipeContainer}>
                  {recipes.map((r, index) => (
                    <div
                      key={r.id}
                      className={styles.recipeChip}
                      draggable={!isRunning}
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(index))
                        e.dataTransfer.effectAllowed = 'move'
                      }}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault()
                        const fromIndex = parseInt(e.dataTransfer.getData('text/plain'))
                        const toIndex = index
                        if (fromIndex !== toIndex) {
                          setRecipes((prev) => {
                            const newRecipes = [...prev]
                            const [moved] = newRecipes.splice(fromIndex, 1)
                            newRecipes.splice(toIndex, 0, moved)
                            // Update history atomically
                            setRecipeHistory((history) => {
                              const newHistory = [...history.slice(0, recipeHistoryIndex + 1), newRecipes]
                              setRecipeHistoryIndex((idx) => idx + 1)
                              return newHistory
                            })
                            return newRecipes
                          })
                        }
                      }}
                    >
                      <button
                        title={r.hint}
                        onClick={() => {
                          // Add a new instance of the recipe (allow multiple selections)
                          setUnifiedOrder((prev) => {
                            const existingIds = new Set(prev.map(i => i.id))
                            const newInstance = {
                              id: generateUniqueId(existingIds),
                              type: 'recipe' as const,
                              content: r.id
                            }
                            const newOrder = [...prev, newInstance]
                            // Save unified order to history to preserve instance IDs
                            setUnifiedOrderHistory((history) => {
                              const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
                              setUnifiedOrderHistoryIndex((idx) => idx + 1)
                              return newHistory
                            })
                            return newOrder
                          })
                        }}
                        className={`${styles.presetButton} ${unifiedOrder.some(i => i.type === 'recipe' && i.content === r.id) ? styles.chipActive : ''}`}
                      >
                        {unifiedOrder.filter(i => i.type === 'recipe' && i.content === r.id).length > 0 ? `✓ (${unifiedOrder.filter(i => i.type === 'recipe' && i.content === r.id).length}) ` : ''}{r.label}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Advanced overrides */}
              <div className={styles.advancedOverrides}>
                <label className={`${styles.label} ${styles.marginBottom6}`} title="Additional options for selected skills">Advanced</label>
                <div className={styles.advancedOverridesContainer}>
                  {selectedSkills.includes('graphrag_query') && (
                    <label className={styles.advancedOverride} title="Choose entity-centric (local) or thematic (global) analysis">
                      GraphRAG method:
                      <select value={graphragMethod} onChange={(e) => setGraphragMethod(e.target.value as any)} className={styles.advancedOverrideSelect}>
                        <option value="local">local (entity)</option>
                        <option value="global">global (thematic)</option>
                      </select>
                    </label>
                  )}
                  {selectedSkills.includes('ollama_generate') && (
                    <label className={styles.advancedOverride} title="Specify which Ollama model to use">
                      Ollama model:
                      <input
                        value={ollamaModel}
                        onChange={(e) => setOllamaModel(e.target.value)}
                        placeholder="e.g. llama3.2"
                        className={styles.advancedOverrideInput}
                      />
                    </label>
                  )}
                  {(selectedSkills.includes('autonomi_upload') || selectedSkills.includes('autonomi_download') || selectedSkills.includes('autonomi_status')) && (
                    <>
                      <label className={styles.advancedOverride} title="Your Autonomi private key for authentication">
                        Autonomi key:
                        <input
                          type="password"
                          value={autonomiKey}
                          onChange={(e) => setAutonomiKey(e.target.value)}
                          placeholder="private key"
                          className={styles.advancedOverrideInput}
                        />
                      </label>
                      <label className={styles.advancedOverride} title="Choose testnet for development or mainnet for production">
                        Autonomi network:
                        <select value={autonomiNetwork} onChange={(e) => setAutonomiNetwork(e.target.value as any)} className={styles.advancedOverrideSelect}>
                          <option value="testnet">testnet</option>
                          <option value="mainnet">mainnet</option>
                        </select>
                      </label>
                      {selectedSkills.includes('autonomi_upload') && (
                        <label className={styles.advancedOverride} title="Make uploaded files publicly accessible">
                          Public:
                          <input
                            type="checkbox"
                            checked={autonomiPublic}
                            onChange={(e) => setAutonomiPublic(e.target.checked)}
                            className={styles.advancedOverrideCheckbox}
                          />
                        </label>
                      )}
                      {selectedSkills.includes('autonomi_download') && (
                        <label className={styles.advancedOverride} title="Address of file to download (from previous upload)">
                          Autonomi address:
                          <input
                            value={autonomiAddress}
                            onChange={(e) => setAutonomiAddress(e.target.value)}
                            placeholder="address from upload"
                            className={styles.advancedOverrideInput}
                          />
                        </label>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RUN */}
      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong title="Execute selected skills and monitor execution">Run</strong>
          <button
            onClick={() => setTipsPopupOpen(true)}
            className={styles.skillGuideButton}
            title="View tips"
          >
            💡
          </button>
        </div>
        <div className={styles.presetsContainer}>
          <button
            onClick={runStream}
            disabled={!canRun}
            className={styles.runButton}
            title={isRunning ? 'Currently running' : 'Execute selected skills in sequence'}
          >
            {isRunning ? '⏳ Running…' : '▶ Run Stream'}
          </button>
          {isRunning && (
            <button
              onClick={stopStream}
              disabled={isStopping}
              className={styles.stopButton}
              title={isStopping ? 'Stopping...' : 'Abort current run'}
            >
              {isStopping ? '⏳ Stopping…' : '⏹ Stop'}
            </button>
          )}
          {(isRunning || isStopping) && (
            <span className={styles.runStatus}>
              {isStopping ? 'Stopping' : currentSkill} • {Math.floor((Date.now() - startTime) / 1000)}s
            </span>
          )}
          <button onClick={clearEvents} className={styles.clearEventsButton} title="Clear event history from display">
            Clear Events
          </button>
        </div>
        <div className={styles.statusText} title="Current system status">
          Status: {isStopping ? 'Stopping' : isRunning ? 'Running' : 'Idle'} · Events: {events.length} · Graph: {graph ? 'Loaded' : 'None'}
          {ingested && <> · Ingested: {ingested.document_count ?? (ingested.documents?.length ?? 0)} docs</>}
        </div>
      </div>

      {ingested && (
        <div className={styles.box} title="Documents processed by doc_ingest skill">
          <strong>Ingested documents</strong>
          {ingested.warning && <div className={styles.ingestedWarning}>{ingested.warning}</div>}
          <div className={styles.ingestedList}>
            {(ingested.documents || []).map((d: IngestedDocument, i: number) => (
              <div key={i} className={styles.ingestedItem}>
                <div className={styles.ingestedItemName}>{d.path || d.name || `#${i}`}</div>
                {d.error ? <div className={styles.ingestedItemError}>error: {d.error}</div>
                  : <div className={styles.ingestedItemInfo}>{d.size ? human(d.size) : ''}{d.type ? ` · ${d.type}` : ''}</div>}
              </div>
            ))}
            {(!ingested.documents || ingested.documents.length === 0) && !ingested.warning && (
              <div className={styles.ingestedEmpty}>(no documents)</div>
            )}
          </div>
        </div>
      )}

      {ollama && (
        <div className={styles.box} title="Response from Ollama LLM">
          <div className={styles.ollamaResponseHeader}>
            <strong>🦙 Ollama response</strong>
            <span className={styles.ollamaResponseInfo}>
              {ollama.model} · status: {ollama.status}
              {typeof ollama.documents_used === 'number' && <> · {ollama.documents_used} docs</>}
              {typeof ollama.context_chars === 'number' && <> · {ollama.context_chars} chars context</>}
            </span>
          </div>
          {ollama.error && <div className={styles.ollamaError}>Error: {ollama.error}</div>}
          {ollama.response && (
            <pre className={styles.ollamaResponse}>
              {ollama.response}
            </pre>
          )}
        </div>
      )}

      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong title="Real-time execution events from skills">Events ({events.length})</strong>
          <button
            onClick={() => setTipsPopupOpen(true)}
            className={styles.skillGuideButton}
            title="View tips"
          >
            💡
          </button>
        </div>
        <div className={styles.sectionWithTips}>
          <div className={styles.sectionContent}>
            <div className={styles.eventsContainer}>
              <pre className={styles.eventsPre}>
                {JSON.stringify(events.slice(-50), null, 2)}
              </pre>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong title="Visualizes dependencies and relationships">Dependency Graph</strong>
          <button
            onClick={() => setTipsPopupOpen(true)}
            className={styles.skillGuideButton}
            title="View tips"
          >
            💡
          </button>
        </div>
        <div className={styles.sectionWithTips}>
          <div className={styles.sectionContent}>
            <div className={styles.graphContainer}>
              <ReactFlow nodes={nodes} edges={edges} fitView>
                <Background />
              </ReactFlow>
            </div>
          </div>
        </div>
      </div>

      {skillGuideOpen && (
        <div
          onClick={() => setSkillGuideOpen(false)}
          className={styles.skillGuideModalOverlay}
        >
          <div
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
            className={styles.skillGuideModalContent}
          >
            <div className={styles.skillGuideModalHeader}>
              <strong>Skill Guide</strong>
              <button
                onClick={() => setSkillGuideOpen(false)}
                className={styles.modalCloseButton}
              >
                ✕
              </button>
            </div>
            <div className={styles.skillGuideModalBody}>
              <SkillGuide />
            </div>
          </div>
        </div>
      )}

      {tipsPopupOpen && (
        <div ref={tipsPopupRef} className={styles.tipsPopup}>
          <div className={styles.tipsPopupHeader}>
            <span className={styles.tipsPopupTitle}>Tips</span>
            <button
              onClick={() => setTipsPopupOpen(false)}
              className={styles.tipsPopupClose}
            >
              ✕
            </button>
          </div>

          {/* Documents Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Documents')}
              title="Click to expand/collapse Documents tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Documents</span>
              <span>{expandedTipSections['Documents'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Documents'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Upload files</strong> by dragging them into the drop zone or clicking to browse</li>
                  <li><strong>Supported formats</strong>: PDF, DOCX, XLSX, IPYNB, Parquet, Markdown, code files (Python, TS, JS, JSON, etc.), and data files</li>
                  <li><strong>File size limit</strong>: 50MB per file to ensure smooth processing</li>
                  <li><strong>Library</strong> stores uploaded files for reuse across sessions - files persist on the server</li>
                  <li><strong>Presets</strong> are quick shortcuts to common project directories configured by the admin</li>
                  <li><strong>input_path</strong> specifies which files/folders skills will process - can be a single file or entire directory</li>
                  <li><strong>Recent</strong> tracks your last 8 used paths for quick re-access</li>
                  <li><strong>Best practice</strong>: Upload related documents together, then use the library path as input_path for batch processing</li>
                  <li><strong>Pick folder</strong>: Use the file picker to browse the project structure and select specific directories</li>
                </ul>
              </div>
            )}
          </div>

          {/* Goal Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Goal')}
              title="Click to expand/collapse Goal tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Goal</span>
              <span>{expandedTipSections['Goal'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Goal'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Be specific</strong> about what you want to accomplish - vague goals lead to generic results</li>
                  <li><strong>Use templates</strong> for common tasks (click the buttons below the goal input)</li>
                  <li><strong>The goal guides the AI</strong> in how to process your documents - it's the instruction for all downstream skills</li>
                  <li><strong>Good examples</strong>: "Summarize the architecture focusing on data flow", "Find all security vulnerabilities in the authentication module", "Generate API documentation for the REST endpoints", "Extract and explain the key design patterns used"</li>
                  <li><strong>Poor examples</strong>: "Summarize this", "Look at the code", "Tell me about it" - too vague</li>
                  <li><strong>Combine with skills</strong>: Different goals work better with different skill combinations (e.g., dependency analysis vs. summarization)</li>
                  <li><strong>Iterate</strong>: Start with a simple goal, then refine based on results</li>
                </ul>
              </div>
            )}
          </div>

          {/* Skills Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Skills')}
              title="Click to expand/collapse Skills tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Skills</span>
              <span>{expandedTipSections['Skills'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Skills'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>doc_ingest</strong> must be first to read files into context - without it, other skills have no data to process</li>
                  <li><strong>Skill order matters</strong>: Skills execute sequentially, with each receiving the output of previous skills</li>
                  <li><strong>Recipes</strong> provide pre-configured skill combinations for common workflows - use them as starting points</li>
                  <li><strong>AI/LLM skills</strong> require API keys (set in environment) or local services (Ollama, LM Studio must be running)</li>
                  <li><strong>Advanced options</strong> appear dynamically when relevant skills are selected (e.g., GraphRAG method, Ollama model)</li>
                  <li><strong>Skill dependencies</strong>: Some skills require specific outputs from earlier skills (e.g., graphrag_query needs graphrag_index first)</li>
                  <li><strong>Hover over skills</strong> to see descriptions of what each skill does</li>
                  <li><strong>Collapse/expand groups</strong> to focus on specific skill categories</li>
                  <li><strong>Clear selection</strong> by clicking selected skills again to deselect them</li>
                </ul>
              </div>
            )}
          </div>

          {/* Skill Groups */}
          {SKILL_GROUPS.map((group) => (
            <div key={group.name} className={styles.tipsPopupSection}>
              <div
                className={styles.tipsPopupSectionHeader}
                onClick={() => toggleTipSection(group.name)}
                title={`Click to expand/collapse ${group.name} tips`}
              >
                <span className={styles.tipsPopupSectionTitle}>{group.name}</span>
                <span>{expandedTipSections[group.name] ? '▼' : '▶'}</span>
              </div>
              {expandedTipSections[group.name] && (
                <div className={styles.tipsPopupSectionContent}>
                  <ul>
                    {group.name === 'Core UAR' && (
                      <>
                        <li><strong>doc_ingest</strong>: Reads files from input_path into context - parses documents and extracts content for downstream skills</li>
                        <li><strong>dependency_map</strong>: Builds dependency graph between artifacts - analyzes imports, references, and relationships to map codebase structure</li>
                        <li><strong>section_sum</strong>: Summarizes document sections - breaks down long documents into digestible section summaries</li>
                        <li><strong>sum_review</strong>: Final review of pipeline outputs - synthesizes all previous skill outputs into a cohesive summary</li>
                        <li><strong>Typical workflow</strong>: doc_ingest → dependency_map → section_sum → sum_review for comprehensive codebase analysis</li>
                      </>
                    )}
                    {group.name === 'AI / LLM' && (
                      <>
                        <li><strong>Ollama</strong>: Local models (requires Ollama running locally) - supports llama3, mistral, codellama and more</li>
                        <li><strong>OpenAI</strong>: GPT models (requires OPENAI_API_KEY) - GPT-4, GPT-3.5 for chat, completion, and embeddings</li>
                        <li><strong>LM Studio</strong>: Local models (requires LM Studio running) - run local LLMs with a GUI interface</li>
                        <li><strong>Anthropic</strong>: Claude models (requires ANTHROPIC_API_KEY) - Claude 3 Opus, Sonnet, Haiku for high-quality reasoning</li>
                        <li><strong>Gemini</strong>: Google models (requires GEMINI_API_KEY) - Gemini Pro for multimodal capabilities</li>
                        <li><strong>Mistral</strong>: Mistral models (requires MISTRAL_API_KEY) - Mistral 7B, Mixtral for efficient inference</li>
                        <li><strong>Groq</strong>: Ultra-fast inference (requires GROQ_API_KEY) - LPU acceleration for real-time responses</li>
                        <li><strong>Hugging Face</strong>: HF models (requires HF_API_KEY) - Access thousands of models via HF Inference API</li>
                        <li><strong>Together</strong>: Together models (requires TOGETHER_API_KEY) - Optimized open-source models with fast inference</li>
                        <li><strong>Optuna</strong>: Hyperparameter optimization - automated tuning for ML models, distributed optimization (requires optuna)</li>
                        <li><strong>AutoGluon</strong>: AutoML with ensemble methods - automated ML with stacking, multi-modal support (requires autogluon)</li>
                        <li><strong>PyCaret</strong>: Low-code ML - classification, regression, clustering, anomaly detection (requires pycaret)</li>
                        <li><strong>FLAML</strong>: Efficient AutoML - fast hyperparameter tuning, resource-efficient (requires flaml)</li>
                        <li><strong>ChromaDB</strong>: Vector database - semantic search, embeddings storage, RAG backend (requires chromadb)</li>
                        <li><strong>Choosing a provider</strong>: Local (Ollama/LM Studio) for privacy/privacy, cloud APIs for better models/speed</li>
                      </>
                    )}
                    {group.name === 'GraphRAG' && (
                      <>
                        <li><strong>graphrag_init</strong>: One-time workspace setup - initializes GraphRAG configuration and directories</li>
                        <li><strong>graphrag_index</strong>: Build knowledge graph (slow, one-time) - extracts entities, relationships, and community structure from documents</li>
                        <li><strong>graphrag_query</strong>: Query the index with metadata - ask natural language questions against the knowledge graph</li>
                        <li><strong>Methods</strong>: Local (entity-centric) for detailed analysis, Global (thematic) for high-level insights</li>
                        <li><strong>Use case</strong>: Best for large document collections where you need to understand relationships and themes</li>
                        <li><strong>Workflow</strong>: Run init once, then index once per dataset, then query as many times as needed</li>
                        <li><strong>Performance</strong>: Indexing is computationally expensive - budget time for large datasets</li>
                      </>
                    )}
                    {group.name === 'Autonomi' && (
                      <>
                        <li><strong>autonomi_upload</strong>: Upload to decentralized storage - stores files on the Autonomi network with content addressing</li>
                        <li><strong>autonomi_download</strong>: Download by address - retrieve files using the address returned from upload</li>
                        <li><strong>autonomi_status</strong>: Check connectivity and wallet - verifies Autonomi client is running and wallet is configured</li>
                        <li><strong>Requirements</strong>: autonomi package installed, wallet with tokens for upload operations</li>
                        <li><strong>Network</strong>: Choose testnet for development, mainnet for production storage</li>
                        <li><strong>Public option</strong>: When uploading, choose whether to make files publicly accessible or private</li>
                        <li><strong>Use case</strong>: Permanent, decentralized storage for important documents and datasets</li>
                      </>
                    )}
                    {group.name === 'ALM' && (
                      <>
                        <li><strong>alm_analyze</strong>: Analyze grammar specifications - parses BNF, EBNF, and other formal grammar definitions</li>
                        <li><strong>alm_generate</strong>: Generate token sequences - produces valid sequences following grammar rules from a given prefix</li>
                        <li><strong>alm_verify</strong>: Validate against grammar - checks if text conforms to the specified grammar rules</li>
                        <li><strong>Requirements</strong>: ALM service running (separate service dependency)</li>
                        <li><strong>Use cases</strong>: Code generation, data format validation, protocol testing, formal language processing</li>
                        <li><strong>Workflow</strong>: Analyze grammar first, then generate sequences, verify outputs as needed</li>
                      </>
                    )}
                    {group.name === 'STEM' && (
                      <>
                        <li><strong>math_compute</strong>: Symbolic math with SymPy - solve equations, differentiate, integrate, simplify expressions</li>
                        <li><strong>cipher_ops</strong>: Cryptographic operations - encrypt/decrypt data, hash functions, digital signatures</li>
                        <li><strong>physics_compute</strong>: Physics & astronomy calculations - unit conversions, coordinate transforms, cosmology computations</li>
                        <li><strong>diff_eq_solve</strong>: Differential equations with diffeqpy - solve ODE/PDE systems, symbolic optimization, fast solvers</li>
                        <li><strong>cern_root</strong>: CERN ROOT data analysis - particle physics data processing, large dataset analysis, statistical methods</li>
                        <li><strong>scipy_opt</strong>: SciPy optimization - linear/nonlinear programming, integration, interpolation, eigenvalue problems</li>
                        <li><strong>quantum_circuit</strong>: Quantum computing with Qiskit - build quantum circuits, run on IBM Q, implement quantum algorithms</li>
                        <li><strong>quantum_ml</strong>: Quantum ML with PennyLane - quantum neural networks, quantum chemistry, hybrid quantum-classical models</li>
                        <li><strong>chem_analysis</strong>: Computational chemistry with RDKit - molecular analysis, conformer generation, chemical properties</li>
                        <li><strong>bio_compute</strong>: Bioinformatics with Biopython - DNA/RNA/protein analysis, sequence alignment, structure prediction</li>
                        <li><strong>relativity</strong>: General relativity with EinsteinPy - spacetime metrics, geodesics, gravitational physics calculations</li>
                        <li><strong>data_viz_3d</strong>: 3D visualization with PyVista - mesh analysis, VTK integration, scientific 3D plotting</li>
                        <li><strong>Requirements</strong>: sympy, pycryptodome, astropy, diffeqpy, root-cern, scipy, qiskit, pennylane, rdkit, biopython, einsteinpy, pyvista</li>
                        <li><strong>Use cases</strong>: Scientific computing, particle physics, quantum computing, computational chemistry, bioinformatics, relativity research</li>
                        <li><strong>Integration</strong>: Combine with doc_ingest to process scientific papers, research data, and technical documentation</li>
                      </>
                    )}
                    {group.name === 'Hardware / Embedded' && (
                      <>
                        <li><strong>fpga_verify</strong>: FPGA verification with cocotb - Python testbenches for Verilog/SystemVerilog, works with major simulators</li>
                        <li><strong>verilog_parse</strong>: Verilog HDL processing with Pyverilog - parser, code analysis, code generation for RTL design</li>
                        <li><strong>myhdl_design</strong>: Hardware design with MyHDL - Python to Verilog/VHDL conversion, simulation, hardware description in Python</li>
                        <li><strong>riscv_sim</strong>: RISC-V simulation with riscemu - emulator for RISC-V assembly programs, symbol support, flexible execution</li>
                        <li><strong>riscv_cycle</strong>: Cycle-accurate RISC-V with py-v - CPU simulator, RTL modeling library, precise timing analysis</li>
                        <li><strong>verilator_sim</strong>: Verilog simulation with Verilator - high-speed SystemVerilog to C++/SystemC conversion, fast simulation</li>
                        <li><strong>micropython</strong>: MicroPython for embedded - ESP32/ESP8266 programming, microcontroller development, IoT applications</li>
                        <li><strong>platformio</strong>: Embedded development with PlatformIO - Arduino, ESP32, STM32 support, CI/CD integration, team collaboration</li>
                        <li><strong>Requirements</strong>: cocotb, pyverilog, myhdl, riscemu, py-v, verilator, micropython, platformio</li>
                        <li><strong>Use cases</strong>: FPGA design verification, RISC-V processor simulation, embedded systems development, IoT programming</li>
                        <li><strong>Workflow</strong>: Design hardware in Python/HDL, simulate with emulators, deploy to FPGAs or microcontrollers</li>
                      </>
                    )}
                    {group.name === 'Computer Vision' && (
                      <>
                        <li><strong>yolo_detect</strong>: Object detection with YOLO - real-time detection, custom training on your own datasets</li>
                        <li><strong>opencv_process</strong>: Image processing with OpenCV - filters, transforms, edge detection, feature extraction</li>
                        <li><strong>video_analyze</strong>: Video analysis - motion detection, object tracking, frame extraction, stream processing</li>
                        <li><strong>face_recognize</strong>: Face recognition - detection, identification, emotion analysis, age estimation</li>
                        <li><strong>Requirements</strong>: ultralytics, opencv-python, face_recognition, numpy, pillow</li>
                        <li><strong>Use cases</strong>: Object detection in images/videos, surveillance, biometrics, image enhancement</li>
                        <li><strong>Performance</strong>: GPU acceleration recommended for real-time video processing</li>
                      </>
                    )}
                    {group.name === 'Blockchain / Web3' && (
                      <>
                        <li><strong>web3_eth</strong>: Ethereum interaction with web3.py - smart contracts, transactions, blockchain queries</li>
                        <li><strong>solana_tx</strong>: Solana transactions - SPL tokens, wallet management, high-speed transactions</li>
                        <li><strong>smart_contract</strong>: Smart contract deployment - Solidity contracts, deployment, interaction, testing</li>
                        <li><strong>nft_mint</strong>: NFT minting - ERC-721/1155 tokens, metadata, IPFS integration</li>
                        <li><strong>Requirements</strong>: web3, solana-py, brownie, eth-account, wallet provider</li>
                        <li><strong>Use cases</strong>: DeFi applications, NFT marketplaces, tokenized assets, blockchain integration</li>
                        <li><strong>Networks</strong>: Testnets for development (Goerli, Sepolia), mainnets for production</li>
                      </>
                    )}
                    {group.name === 'MLOps' && (
                      <>
                        <li><strong>mlflow_track</strong>: ML experiment tracking with MLflow - metrics, parameters, artifacts, reproducibility</li>
                        <li><strong>mlflow_deploy</strong>: ML model deployment - serving, batch inference, REST APIs, Docker containers</li>
                        <li><strong>kubeflow_pipe</strong>: ML pipelines with Kubeflow - workflow orchestration on Kubernetes, scalable pipelines</li>
                        <li><strong>model_reg</strong>: Model registry - versioning, staging, promotion, lifecycle management</li>
                        <li><strong>Requirements</strong>: mlflow, kfp, kubernetes, docker, cloud storage</li>
                        <li><strong>Use cases</strong>: Experiment tracking, model deployment, pipeline orchestration, reproducible ML</li>
                        <li><strong>Integration</strong>: Works with most ML frameworks (PyTorch, TensorFlow, scikit-learn)</li>
                      </>
                    )}
                    {group.name === 'Security' && (
                      <>
                        <li><strong>pentest_scan</strong>: Penetration testing - vulnerability scanning, security assessment, exploit testing</li>
                        <li><strong>osint_recon</strong>: OSINT reconnaissance - gather intelligence on targets, subdomain enumeration, data collection</li>
                        <li><strong>crypto_analyze</strong>: Cryptographic analysis - hash cracking, encryption analysis, key management</li>
                        <li><strong>security_audit</strong>: Security audit - code review, dependency vulnerabilities, compliance checking</li>
                        <li><strong>Requirements</strong>: nmap, python-nmap, requests, shodan, hashcat, pycryptodome, bandit, safety</li>
                        <li><strong>Use cases</strong>: Security assessment, vulnerability management, compliance auditing, threat analysis</li>
                        <li><strong>Legal</strong>: Only use on systems you own or have explicit permission to test</li>
                      </>
                    )}
                    {group.name === 'Data Engineering' && (
                      <>
                        <li><strong>airflow_dag</strong>: Workflow orchestration with Airflow - DAGs, scheduling, monitoring, dependencies</li>
                        <li><strong>dbt_transform</strong>: Data transformation with dbt - SQL models, testing, documentation, data quality</li>
                        <li><strong>snowflake_etl</strong>: Snowflake ETL - data loading, warehousing, analytics, cloud data platform</li>
                        <li><strong>spark_process</strong>: Big data processing with PySpark - ETL, analytics on large datasets, distributed computing</li>
                        <li><strong>Requirements</strong>: apache-airflow, dbt-core, snowflake-connector-python, pyspark, jupyter</li>
                        <li><strong>Use cases</strong>: Data pipelines, ETL workflows, data warehousing, big data analytics</li>
                        <li><strong>Infrastructure</strong>: Requires cloud platforms or on-premise clusters for production</li>
                      </>
                    )}
                  </ul>
                </div>
              )}
            </div>
          ))}

          {/* Run Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Run')}
              title="Click to expand/collapse Run tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Run</span>
              <span>{expandedTipSections['Run'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Run'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Run Stream</strong> executes selected skills in sequence with real-time event updates - skills run one after another</li>
                  <li><strong>Stop button</strong> appears during execution to abort the current run - useful if a skill is taking too long or you made a mistake</li>
                  <li><strong>Clear Events</strong> removes previous run data from the display - doesn't affect the server, just the UI</li>
                  <li><strong>Status bar</strong> shows running state, event count, and graph availability - monitor progress at a glance</li>
                  <li><strong>Execution time</strong> and current skill are displayed while running - track which skill is active and total duration</li>
                  <li><strong>Prerequisites</strong>: Goal must be non-empty and at least one skill must be selected to enable the Run button</li>
                  <li><strong>Event limit</strong>: System stops after 1000 events to prevent memory issues - large runs may need to be split</li>
                  <li><strong>Error handling</strong>: Errors are displayed in the error box with details and copy functionality</li>
                  <li><strong>Concurrency</strong>: Only one run at a time - the Run button is disabled while another run is in progress</li>
                  <li><strong>Streaming</strong>: Events stream in real-time via Server-Sent Events - you see progress as it happens</li>
                </ul>
              </div>
            )}
          </div>

          {/* Events Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Events')}
              title="Click to expand/collapse Events tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Events</span>
              <span>{expandedTipSections['Events'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Events'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Events</strong> show real-time execution details from each skill - JSON-formatted log of what's happening</li>
                  <li><strong>Display limit</strong>: Shows the last 50 events in the UI (full history available in server logs)</li>
                  <li><strong>Event types</strong>: skill_start, skill_complete, error, orchestration_plan, and more</li>
                  <li><strong>skill_start</strong>: Indicates a skill has begun execution - includes skill name and metadata</li>
                  <li><strong>skill_complete</strong>: Indicates a skill finished successfully - includes results and output data</li>
                  <li><strong>error</strong>: Something went wrong - includes error message and context for debugging</li>
                  <li><strong>orchestration_plan</strong>: Shows the execution plan before skills run - useful for understanding workflow</li>
                  <li><strong>Debugging</strong>: Use events to understand execution flow and identify where failures occur</li>
                  <li><strong>JSON format</strong>: Allows for programmatic analysis and export if needed</li>
                  <li><strong>Timestamps</strong>: Each event includes timing information for performance analysis</li>
                </ul>
              </div>
            )}
          </div>

          {/* Graph Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Graph')}
              title="Click to expand/collapse Dependency Graph tips"
            >
              <span className={styles.tipsPopupSectionTitle}>Dependency Graph</span>
              <span>{expandedTipSections['Graph'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Graph'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Dependency Graph</strong> visualizes relationships between artifacts in your codebase</li>
                  <li><strong>Generation</strong>: Created by skills like dependency_map and GraphRAG - different skills produce different graph types</li>
                  <li><strong>Nodes</strong> represent files, skills, or entities depending on the graph type - labeled with names/types</li>
                  <li><strong>Edges</strong> show dependencies, relationships, or data flow between nodes - arrows indicate direction</li>
                  <li><strong>Interactive controls</strong>: Drag to pan, scroll to zoom, click nodes for details (if supported)</li>
                  <li><strong>Use cases</strong>: Understand codebase structure, identify circular dependencies, visualize data flow</li>
                  <li><strong>dependency_map graphs</strong>: Show file imports, function calls, and module dependencies</li>
                  <li><strong>GraphRAG graphs</strong>: Show entities, relationships, and communities extracted from documents</li>
                  <li><strong>Layout</strong>: Automatic grid layout - nodes arranged in rows for readability</li>
                  <li><strong>Background</strong>: Dotted grid helps with spatial orientation and alignment</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Library Popup */}
      {libraryPopupOpen && (
        <div className={styles.modalOverlay} onClick={() => setLibraryPopupOpen(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <strong>📚 Library</strong>
              <button className={styles.modalCloseButton} onClick={() => setLibraryPopupOpen(false)}>✕</button>
            </div>
            <div className={styles.modalBody}>
              {libBusy ? (
                <div className={styles.loadingText}>Loading library…</div>
              ) : library.length === 0 ? (
                <div className={styles.emptyLibrary}>(empty — upload files to add them)</div>
              ) : (
                <div className={styles.libraryPopupList}>
                  {library.map((f) => (
                    <div
                      key={f.path}
                      className={styles.libraryPopupItem}
                      onClick={() => {
                        onPick(f.path)
                        setLibraryPopupOpen(false)
                      }}
                    >
                      <span className={styles.libraryItemName}>
                        📄 {f.name}
                      </span>
                      <span className={styles.libraryItemSize}>
                        {human(f.size)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.footerButton} onClick={() => setLibraryPopupOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Recipes Popup */}
      {recipesPopupOpen && (
        <div className={styles.modalOverlay} onClick={() => setRecipesPopupOpen(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <strong>📚 Recipes Library</strong>
              <button className={styles.modalCloseButton} onClick={() => setRecipesPopupOpen(false)}>✕</button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.libraryPopupList}>
                {recipes.map((r) => (
                  <div
                    key={r.id}
                    className={styles.libraryPopupItem}
                    onClick={() => {
                      // Add a new instance of the recipe (allow multiple selections)
                      setUnifiedOrder((prev) => {
                        const existingIds = new Set(prev.map(i => i.id))
                        const newInstance = {
                          id: generateUniqueId(existingIds),
                          type: 'recipe' as const,
                          content: r.id
                        }
                        const newOrder = [...prev, newInstance]
                        // Save unified order to history to preserve instance IDs
                        setUnifiedOrderHistory((history) => {
                          const newHistory = [...history.slice(0, unifiedOrderHistoryIndex + 1), newOrder]
                          setUnifiedOrderHistoryIndex((idx) => idx + 1)
                          return newHistory
                        })
                        return newOrder
                      })
                    }}
                  >
                    <span className={styles.libraryItemName}>
                      {unifiedOrder.filter(i => i.type === 'recipe' && i.content === r.id).length > 0 ? `✓ (${unifiedOrder.filter(i => i.type === 'recipe' && i.content === r.id).length}) ` : ''}{r.label}
                    </span>
                    <span className={styles.libraryItemSize}>
                      {r.skills.join(', ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.footerButton} onClick={() => setRecipesPopupOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UARPanel
