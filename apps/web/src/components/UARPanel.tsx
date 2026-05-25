import { useMemo, useState, useRef, useCallback, useEffect, lazy, Suspense } from 'react'
import { MetricsDashboard } from './MetricsDashboard'
import { FilePicker } from './FilePicker'
import type { Preset } from './FilePicker'
import { SkillGuide } from './SkillGuide'
import { useDarkMode } from '../hooks/useDarkMode'
import { usePreload } from '../hooks/usePreload'
import { generateUniqueId } from '../utils/idGenerator'
import RecipeTimeline from './RecipeTimeline'
import { HealthDashboard } from './HealthDashboard'
import styles from './UARPanel.module.css'

function getLocalStorage(): Storage | null {
  try {
    const storage = globalThis.localStorage
    if (
      storage &&
      typeof storage.getItem === 'function' &&
      typeof storage.setItem === 'function' &&
      typeof storage.removeItem === 'function'
    ) {
      return storage
    }
  } catch {
    // localStorage can be unavailable in tests, SSR, or privacy modes.
  }
  return null
}

// Helper to build Authorization header when API key is present
function authHeaders(init?: Record<string, string>): Record<string, string> {
  const key = getLocalStorage()?.getItem('uar_api_key')
  if (!key) return init || {}
  return { Authorization: `Bearer ${key}`, ...init }
}

// Lazy-loaded visualizers — only fetched when their skill data arrives
const GraphVisualizer = lazy(() =>
  import('./GraphVisualizer').then((m) => ({ default: m.GraphVisualizer })))
const TrefoilKnotVisualizer = lazy(() =>
  import('./TrefoilKnotVisualizer').then((m) => ({ default: m.TrefoilKnotVisualizer })))
const MolecularVisualizer = lazy(() =>
  import('./MolecularVisualizer').then((m) => ({ default: m.MolecularVisualizer })))
const QuantumCircuitVisualizer = lazy(() =>
  import('./QuantumCircuitVisualizer').then((m) => ({ default: m.QuantumCircuitVisualizer })))
const PhysicsVisualizer = lazy(() =>
  import('./PhysicsVisualizer').then((m) => ({ default: m.PhysicsVisualizer })))
const MathVisualizer = lazy(() =>
  import('./MathVisualizer').then((m) => ({ default: m.MathVisualizer })))
const RiscvVisualizer = lazy(() =>
  import('./RiscvVisualizer').then((m) => ({ default: m.RiscvVisualizer })))
const VerilogVisualizer = lazy(() =>
  import('./VerilogVisualizer').then((m) => ({ default: m.VerilogVisualizer })))
const FpgaVisualizer = lazy(() =>
  import('./FpgaVisualizer').then((m) => ({ default: m.FpgaVisualizer })))
const CipherDashboard = lazy(() =>
  import('./CipherDashboard').then((m) => ({ default: m.CipherDashboard })))
const EcosystemDashboard = lazy(() =>
  import('./EcosystemDashboard').then((m) => ({ default: m.EcosystemDashboard })))
const DocIngestDashboard = lazy(() =>
  import('./DocIngestDashboard').then((m) => ({ default: m.DocIngestDashboard })))
const AutonomiDashboard = lazy(() =>
  import('./AutonomiDashboard').then((m) => ({ default: m.AutonomiDashboard })))
const DataViz3D = lazy(() =>
  import('./DataViz3D').then((m) => ({ default: m.DataViz3D })))
const MathPlotVisualizer = lazy(() =>
  import('./MathPlotVisualizer').then((m) => ({ default: m.MathPlotVisualizer })))

const MAX_EVENTS = 1000
const RECENT_KEY = 'uar.recentPaths'
const RECIPES_KEY = 'uar.recipes'
const USER_PRESETS_KEY = 'uar.userPresets'
const RECENT_MAX = 8

interface UserPreset {
  name: string
  goal: string
  inputPath: string
  unifiedOrder: ExecutionOrderItem[]
  useWebSocket: boolean
  useHierarchical: boolean
  graphragMethod: 'local' | 'global'
  ollamaModel: string
  autonomiKey: string
  autonomiNetwork: 'testnet' | 'mainnet'
  autonomiPublic: boolean
  autonomiAddress: string
}

// TypeScript interfaces for type safety
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
      { id: 'groq_embedding', label: 'groq_embedding', desc: 'Generate embeddings with Groq (requires openai package + GROQ_API_KEY)' },
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
    name: 'UOR Ecosystem',
    icon: '🌐',
    skills: [
      { id: 'uor_addr_canonicalize', label: 'uor_addr_canonicalize', desc: 'Canonicalize data per UOR-ADDR-1 and compute SHA-256 digest' },
      { id: 'uor_addr_resolve',      label: 'uor_addr_resolve',      desc: 'Resolve a UOR digest from the integrator object cache' },
      { id: 'hologram_query',        label: 'hologram_query',        desc: 'Submit geometric inference to gethologram.ai (requires HOLOGRAM_API_KEY)' },
      { id: 'hologram_status',       label: 'hologram_status',       desc: 'Check gethologram.ai service health' },
      { id: 'moltbook_list',         label: 'moltbook_list',         desc: 'List recent topics from moltbook.com/m/uor forum' },
      { id: 'moltbook_search',       label: 'moltbook_search',       desc: 'Search moltbook.com/m/uor forum posts' },
      { id: 'moltbook_post',         label: 'moltbook_post',         desc: 'Post a new topic to moltbook forum (requires MOLTBOOK_API_KEY)' },
      { id: 'prism_btc_anchor',      label: 'prism_btc_anchor',      desc: 'Anchor a UOR digest on Bitcoin (placeholder - pending public API)' },
      { id: 'prism_btc_verify',      label: 'prism_btc_verify',      desc: 'Verify an on-chain Bitcoin anchor (placeholder - pending public API)' },
      { id: 'severance_infer',       label: 'severance_infer',       desc: 'Run inference via Severance AI (placeholder - pending public API)' },
      { id: 'severance_verify',      label: 'severance_verify',      desc: 'Verify Severance AI output (placeholder - pending public API)' },
      { id: 'anunix_health',         label: 'anunix_health',         desc: 'Check Anunix host health (placeholder - pending public API)' },
      { id: 'anunix_run',            label: 'anunix_run',            desc: 'Run command on Anunix host (placeholder - pending public API)' },
      { id: 'uor_ecosystem_status',  label: 'uor_ecosystem_status',  desc: 'Check status of all UOR ecosystem integrations' },
    ]
  },
  {
    name: 'STEM',
    icon: '🔬',
    skills: [
      { id: 'math_compute',    label: 'math_compute',    desc: 'Symbolic math with SymPy: solve, differentiate, integrate, simplify (requires sympy)' },
      { id: 'math_plot',       label: 'math_plot',       desc: '2D mathematical plotting with matplotlib: functions, parametric, polar, scatter (requires matplotlib+numpy)' },
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
      { id: 'trefoil_simulation', label: 'trefoil_simulation', desc: 'Triple trefoil knot quaternion equilibrium: Clifford torus skeleton with Frenet frame rotation and emergent singularity core (requires numpy)' },
      { id: 'molecular_visualization', label: 'molecular_visualization', desc: '3D molecular structures: water, methane, benzene, caffeine, protein backbone with bond topology (no deps)' },
      { id: 'quantum_circuit_visualization', label: 'quantum_circuit_visualization', desc: '3D quantum circuit layout: qubit registers, gates, entanglement connections (no deps)' },
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

type Recipe = { id: string; version?: string; label: string; skills: string[]; hint: string }
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
  { id: 'eco_status', label: '🌐 Ecosystem status',  skills: ['uor_ecosystem_status'], hint: 'Check all UOR ecosystem integrations' },
  { id: 'eco_canon',  label: '🌐 Canonicalize',     skills: ['uor_addr_canonicalize'], hint: 'Canonicalize data per UOR-ADDR-1' },
  { id: 'eco_foundation', label: '🌐 Foundation verify', skills: ['uor_foundation_verify'], hint: 'Call the live UOR Foundation API' },
]

type LibFile = {
  name: string
  path: string
  size: number
  ext: string
  mtime: number
}

function human(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

// Pre-compute initial state so IDs and localStorage reads are consistent
// across all state initializers.
const INITIAL_SKILLS = ['doc_ingest', 'dependency_map', 'sum_review']
const INITIAL_RECIPES = (() => {
  try {
    const saved = getLocalStorage()?.getItem(RECIPES_KEY)
    return saved ? JSON.parse(saved) : RECIPES
  } catch {
    return RECIPES
  }
})()
const INITIAL_UNIFIED_ORDER: {id: string; type: 'skill' | 'recipe'; content: string}[] = INITIAL_SKILLS.map(skill => ({
  id: generateUniqueId(),
  type: 'skill' as const,
  content: skill
}))

// ============================================================
// Main panel
// ============================================================
export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [inputPath, setInputPath] = useState('')
  const [darkMode, setDarkMode] = useDarkMode()

  // Preload heavy visualizer chunks after initial paint so they are
  // already cached when a skill produces 3D data.
  usePreload([
    () => import('./GraphVisualizer'),
    () => import('./DataViz3D'),
    () => import('./TrefoilKnotVisualizer'),
    () => import('./MolecularVisualizer'),
    () => import('./QuantumCircuitVisualizer'),
    () => import('./PhysicsVisualizer'),
    () => import('./MathVisualizer'),
    () => import('./RiscvVisualizer'),
    () => import('./VerilogVisualizer'),
    () => import('./FpgaVisualizer'),
    () => import('./CipherDashboard'),
    () => import('./EcosystemDashboard'),
    () => import('./DocIngestDashboard'),
    () => import('./AutonomiDashboard'),
    () => import('./MathPlotVisualizer'),
  ], 4000)

  const [skillLastPositions, setSkillLastPositions] = useState<Record<string, number>>(() => {
    const positions: Record<string, number> = {}
    INITIAL_SKILLS.forEach((skill, idx) => positions[skill] = idx)
    return positions
  })
  const skillLastPositionsRef = useRef(skillLastPositions)
  skillLastPositionsRef.current = skillLastPositions
  const [recipes, setRecipes] = useState<Recipe[]>(() => INITIAL_RECIPES)
  const [recipeHistory, setRecipeHistory] = useState<Recipe[][]>(() => [INITIAL_RECIPES])
  const [recipeHistoryIndex, setRecipeHistoryIndex] = useState(0)
  const recipeHistoryIndexRef = useRef(recipeHistoryIndex)
  recipeHistoryIndexRef.current = recipeHistoryIndex
  // Unified order combining both skills and recipes
  const [unifiedOrder, setUnifiedOrder] = useState<{id: string; type: 'skill' | 'recipe'; content: string}[]>(() => INITIAL_UNIFIED_ORDER)
  const [skillHistory, setSkillHistory] = useState<string[][]>(() => [INITIAL_SKILLS])
  const skillHistoryRef = useRef(skillHistory)
  skillHistoryRef.current = skillHistory
  const [skillHistoryIndex, setSkillHistoryIndex] = useState(0)
  const skillHistoryIndexRef = useRef(skillHistoryIndex)
  skillHistoryIndexRef.current = skillHistoryIndex
  // Separate history for unified order to preserve instance IDs during undo/redo
  const [unifiedOrderHistory, setUnifiedOrderHistory] = useState<{id: string; type: 'skill' | 'recipe'; content: string}[][]>(() => [INITIAL_UNIFIED_ORDER])
  const unifiedOrderHistoryRef = useRef(unifiedOrderHistory)
  unifiedOrderHistoryRef.current = unifiedOrderHistory
  const [unifiedOrderHistoryIndex, setUnifiedOrderHistoryIndex] = useState(0)
  const unifiedOrderHistoryIndexRef = useRef(unifiedOrderHistoryIndex)
  unifiedOrderHistoryIndexRef.current = unifiedOrderHistoryIndex
  const recipeHistoryRef = useRef(recipeHistory)
  recipeHistoryRef.current = recipeHistory

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
  const [eventViewMode, setEventViewMode] = useState<'json' | 'timeline'>('timeline')
  const [graph, setGraph] = useState<any>(null)
  const [trefoilData, setTrefoilData] = useState<any>(null)
  const [molecularData, setMolecularData] = useState<any>(null)
  const [quantumData, setQuantumData] = useState<any>(null)
  const [physicsData, setPhysicsData] = useState<any>(null)
  const [mathData, setMathData] = useState<any>(null)
  const [riscvData, setRiscvData] = useState<any>(null)
  const [verilogData, setVerilogData] = useState<any>(null)
  const [fpgaData, setFpgaData] = useState<any>(null)
  const [cipherData, setCipherData] = useState<any>(null)
  const [ecosystemData, setEcosystemData] = useState<any>(null)
  const [docIngestData, setDocIngestData] = useState<any>(null)
  const [autonomiData, setAutonomiData] = useState<any>(null)
  const [dataViz3D, setDataViz3D] = useState<any>(null)
  const [mathPlotData, setMathPlotData] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isStopping, setIsStopping] = useState(false)
  const [useWebSocket, setUseWebSocket] = useState(false)
  const [useHierarchical, setUseHierarchical] = useState(false)
  const [wsStatus, setWsStatus] = useState<'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed' | 'error'>('idle')
  const [metrics, setMetrics] = useState<{total_time_sec: number; event_count: number; cache_hits: number; cache_misses: number; skill_times_ms?: Record<string, number>} | null>(null)
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
  // User presets (save/load panel configuration)
  const [userPresets, setUserPresets] = useState<UserPreset[]>(() => {
    try {
      const saved = getLocalStorage()?.getItem(USER_PRESETS_KEY)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })
  const [userPresetName, setUserPresetName] = useState('')
  // Backend skills for validation consistency
  const [backendSkills, setBackendSkills] = useState<string[]>([])

  // Document management
  const [presets, setPresets] = useState<Preset[]>([])
  const [presetsLoaded, setPresetsLoaded] = useState(false)
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
  const [editingRecipe, setEditingRecipe] = useState<Recipe | null>(null)
  const [editRecipeLabel, setEditRecipeLabel] = useState('')
  const [editRecipeSkills, setEditRecipeSkills] = useState('')
  const [editRecipeHint, setEditRecipeHint] = useState('')
  const [builderMode, setBuilderMode] = useState(true)
  const [builderSkills, setBuilderSkills] = useState<string[]>([])
  const [builderDragIndex, setBuilderDragIndex] = useState<number | null>(null)
  const [runsHistory, setRunsHistory] = useState<any[]>([])
  const [showRunsPanel, setShowRunsPanel] = useState(false)
  const [showHealthDashboard, setShowHealthDashboard] = useState(false)
  const [eventFilter, setEventFilter] = useState<string>('all')
  const [skillSearch, setSkillSearch] = useState<string>('')
  const [expandedTipSections, setExpandedTipSections] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    const sections = ['Documents', 'Goal', 'Skills', 'Run', 'Events', 'Graph', ...SKILL_GROUPS.map(g => g.name)]
    // Only expand key sections by default for better performance
    const keySections = ['Documents', 'Goal']
    sections.forEach(s => initial[s] = keySections.includes(s))
    return initial
  })
  const [tipsTargetSection, setTipsTargetSection] = useState<string | null>(null)
  const [uorImageError, setUorImageError] = useState(false)

  // Expand target section when tips popup opens, collapse others
  useEffect(() => {
    if (tipsPopupOpen && tipsTargetSection) {
      setExpandedTipSections(prev => {
        const updated: Record<string, boolean> = {}
        const sections = ['Documents', 'Goal', 'Skills', 'Run', 'Events', 'Graph', ...SKILL_GROUPS.map(g => g.name)]
        sections.forEach(s => {
          updated[s] = s === tipsTargetSection
        })
        return updated
      })
      setTipsTargetSection(null)
      // Focus on the expanded section header when popup opens
      const target = tipsTargetSection
      let rafId = 0
      rafId = requestAnimationFrame(() => {
        rafId = requestAnimationFrame(() => {
          const sectionHeaders = tipsPopupRef.current?.querySelectorAll('[data-section]')
          if (sectionHeaders) {
            for (const header of sectionHeaders) {
            if ((header as HTMLElement).dataset.section === target) {
              (header as HTMLElement).focus()
              if ('scrollIntoView' in header) {
                (header as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' })
              }
              break
            }
          }
        }
        })
      })
      return () => cancelAnimationFrame(rafId)
    }
  }, [tipsPopupOpen, tipsTargetSection])
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    SKILL_GROUPS.forEach(g => initial[g.name] = true)
    return initial
  })
  const [recent, setRecent] = useState<string[]>(() => {
    try {
      const saved = getLocalStorage()?.getItem(RECENT_KEY)
      return saved ? JSON.parse(saved) : []
    } catch (e) {
      console.warn('Failed to load recent paths from localStorage:', e)
      return []
    }
  })

  // Save recipes to localStorage when they change
  useEffect(() => {
    try {
      getLocalStorage()?.setItem(RECIPES_KEY, JSON.stringify(recipes))
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
  const wsRef = useRef<WebSocket | null>(null)
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

  useEffect(() => () => cleanup(), [])

  const refreshLibrary = useCallback(async () => {
    setLibBusy(true)
    try {
      const r = await fetch('/api/uar/docs/library', { headers: authHeaders() })
      const j = await r.json()
      if (r.ok) {
        setLibrary(j.entries || [])
        setLibraryPath(j.library || '')
      }
    } catch { /* ignore */ }
    finally { setLibBusy(false) }
  }, [])

  useEffect(() => {
    fetch('/api/uar/docs/presets', { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => {
        setPresets(d.presets || [])
        setPresetsLoaded(true)
        setProjectRoot(d.project_root || '')
        if (d.library) {
          setLibraryPath(d.library)
          // Default input_path to the library on first load
          setInputPath((cur) => cur || d.library)
        }
      })
      .catch(() => { setPresetsLoaded(true) })
    refreshLibrary()
    // Fetch backend skills for validation consistency
    fetch('/api/uar/skills', { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => {
        setBackendSkills(d.skills || [])
      })
      .catch(() => {
        // Fallback to AVAILABLE_SKILLS if endpoint fails
        setBackendSkills(AVAILABLE_SKILLS.map(s => s.id))
      })
    // Fetch canonical recipes from backend to eliminate drift
    fetch('/api/uar/recipes', { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => {
        const fetched = (d.recipes || []) as Recipe[]
        if (fetched.length === 0) return
        setRecipes((prev) => {
          // Merge: backend canonical recipes override local ones with same ID,
          // user-created recipes not in backend are preserved.
          const fetchedMap = new Map(fetched.map((r) => [r.id, r]))
          const preserved = prev.filter((r) => !fetchedMap.has(r.id))
          const merged = [...fetched, ...preserved]
          // Save merged result to localStorage
          try {
            getLocalStorage()?.setItem(RECIPES_KEY, JSON.stringify(merged))
          } catch {
            /* ignore quota errors */
          }
          // Reset history to merged recipes
          setRecipeHistory([[...merged]])
          setRecipeHistoryIndex(0)
          return merged
        })
      })
      .catch(() => {
        // Silently fall back to existing localStorage/hardcoded recipes
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
        method: 'POST', headers: authHeaders(), body: fd, signal: ctrl.signal,
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
      clearTimeout(timer)
      setUploadMsg(`Upload error: ${e instanceof Error ? e.message : 'unknown'}`)
    }
  }, [refreshLibrary])

  const deleteLibFile = async (name: string) => {
    if (!confirm(`Delete "${name}" from library?`)) return
    try {
      const r = await fetch(`/api/uar/docs/library?name=${encodeURIComponent(name)}`, { method: 'DELETE', headers: authHeaders() })
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

  // ESC closes all open modals and popups
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPickerOpen(false)
        setTipsPopupOpen(false)
        setSkillGuideOpen(false)
        setLibraryPopupOpen(false)
        setRecipesPopupOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPickerOpen, setTipsPopupOpen, setSkillGuideOpen, setLibraryPopupOpen, setRecipesPopupOpen])

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

  const pushRecent = useCallback((p: string) => {
    if (!p.trim()) return
    setRecent((prev) => {
      const next = [p, ...prev.filter((x) => x !== p)].slice(0, RECENT_MAX)
      try {
        getLocalStorage()?.setItem(RECENT_KEY, JSON.stringify(next))
      } catch (e) {
        console.warn('Failed to save recent paths to localStorage:', e)
      }
      return next
    })
  }, [])

  const clearRecent = () => {
    setRecent([])
    try {
      getLocalStorage()?.removeItem(RECENT_KEY)
    } catch (e) {
      console.warn('Failed to clear recent paths from localStorage:', e)
    }
  }

  const saveUserPreset = useCallback(() => {
    const name = userPresetName.trim()
    if (!name) return
    const preset: UserPreset = {
      name,
      goal,
      inputPath,
      unifiedOrder,
      useWebSocket,
      useHierarchical,
      graphragMethod,
      ollamaModel,
      autonomiKey,
      autonomiNetwork,
      autonomiPublic,
      autonomiAddress,
    }
    setUserPresets((prev) => {
      const next = [...prev.filter((p) => p.name !== name), preset]
      try {
        getLocalStorage()?.setItem(USER_PRESETS_KEY, JSON.stringify(next))
      } catch {
        /* ignore quota errors */
      }
      return next
    })
    setUserPresetName('')
  }, [userPresetName, goal, inputPath, unifiedOrder, useWebSocket, useHierarchical, graphragMethod, ollamaModel, autonomiKey, autonomiNetwork, autonomiPublic, autonomiAddress])

  const loadUserPreset = useCallback((preset: UserPreset) => {
    setGoal(preset.goal)
    setInputPath(preset.inputPath)
    setUnifiedOrder(preset.unifiedOrder)
    setUnifiedOrderHistory([preset.unifiedOrder])
    setUnifiedOrderHistoryIndex(0)
    setUseWebSocket(preset.useWebSocket)
    setUseHierarchical(preset.useHierarchical)
    setGraphragMethod(preset.graphragMethod)
    setOllamaModel(preset.ollamaModel)
    setAutonomiKey(preset.autonomiKey)
    setAutonomiNetwork(preset.autonomiNetwork)
    setAutonomiPublic(preset.autonomiPublic)
    setAutonomiAddress(preset.autonomiAddress)
    const skills = preset.unifiedOrder.filter((i) => i.type === 'skill').map((i) => i.content)
    setSkillHistory([skills])
    setSkillHistoryIndex(0)
    const newPositions: Record<string, number> = {}
    preset.unifiedOrder.forEach((item, index) => {
      if (item.type === 'skill') {
        newPositions[item.content] = index
      }
    })
    setSkillLastPositions(newPositions)
  }, [])

  const deleteUserPreset = useCallback((name: string) => {
    setUserPresets((prev) => {
      const next = prev.filter((p) => p.name !== name)
      try {
        getLocalStorage()?.setItem(USER_PRESETS_KEY, JSON.stringify(next))
      } catch {
        /* ignore quota errors */
      }
      return next
    })
  }, [])

  const addSkill = (id: string) => {
    // Add skill: always add a new instance (use remove button to remove)
    setUnifiedOrder((prev) => {
      // Add a new instance of the skill
      const existingIds = new Set(prev.map(i => i.id))
      const newInstance = {
        id: generateUniqueId(existingIds),
        type: 'skill' as const,
        content: id
      }
      const newOrder = [...prev]
      
      // Calculate insert position using ref to get current value
      const lastPosition = skillLastPositionsRef.current[id] ?? newOrder.length
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
        const idx = skillHistoryIndexRef.current
        const newHistory = [...history.slice(0, idx + 1), newSkills]
        setSkillHistoryIndex((i) => i + 1)
        return newHistory
      })
      setUnifiedOrderHistory((history) => {
        const idx = unifiedOrderHistoryIndexRef.current
        const newHistory = [...history.slice(0, idx + 1), newOrder]
        setUnifiedOrderHistoryIndex((i) => i + 1)
        return newHistory
      })
      return newOrder
    })
  }

  const undoSkills = () => {
    setSkillHistoryIndex((prevIndex) => {
      const history = skillHistoryRef.current
      if (prevIndex > 0 && history.length > 0) {
        const newIndex = prevIndex - 1
        if (newIndex < 0 || newIndex >= history.length) {
          console.warn('Undo would cause skillHistoryIndex to go out of bounds')
          return prevIndex
        }
        return newIndex
      }
      return prevIndex
    })
    setUnifiedOrderHistoryIndex((prevIndex) => {
      const history = unifiedOrderHistoryRef.current
      if (prevIndex > 0 && history.length > 0) {
        const newIndex = prevIndex - 1
        if (newIndex < 0 || newIndex >= history.length) {
          console.warn('Undo would cause unifiedOrderHistoryIndex to go out of bounds')
          return prevIndex
        }
        const newOrder = history[newIndex]
        setUnifiedOrder(newOrder)
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
      const history = skillHistoryRef.current
      if (prevIndex < history.length - 1 && history.length > 0) {
        const newIndex = prevIndex + 1
        if (newIndex < 0 || newIndex >= history.length) {
          console.warn('Redo would cause skillHistoryIndex to go out of bounds')
          return prevIndex
        }
        return newIndex
      }
      return prevIndex
    })
    setUnifiedOrderHistoryIndex((prevIndex) => {
      const history = unifiedOrderHistoryRef.current
      if (prevIndex < history.length - 1 && history.length > 0) {
        const newIndex = prevIndex + 1
        if (newIndex < 0 || newIndex >= history.length) {
          console.warn('Redo would cause unifiedOrderHistoryIndex to go out of bounds')
          return prevIndex
        }
        const newOrder = history[newIndex]
        setUnifiedOrder(newOrder)
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
      const history = recipeHistoryRef.current
      if (prevIndex > 0 && history.length > 0) {
        const newIndex = prevIndex - 1
        const targetRecipes = history[newIndex]
        const orderRecipeIds = new Set(unifiedOrder.filter(i => i.type === 'recipe').map(i => i.content))
        const targetIds = new Set(targetRecipes.map(r => r.id))
        for (const id of orderRecipeIds) {
          if (!targetIds.has(id)) {
            console.warn(`Cannot undo: recipe "${id}" is in execution order`)
            return prevIndex
          }
        }
        setRecipes(targetRecipes)
        return newIndex
      }
      return prevIndex
    })
  }

  const redoRecipes = () => {
    setRecipeHistoryIndex((prevIndex) => {
      const history = recipeHistoryRef.current
      if (prevIndex < history.length - 1 && history.length > 0) {
        const newIndex = prevIndex + 1
        const targetRecipes = history[newIndex]
        const orderRecipeIds = new Set(unifiedOrder.filter(i => i.type === 'recipe').map(i => i.content))
        const targetIds = new Set(targetRecipes.map(r => r.id))
        for (const id of orderRecipeIds) {
          if (!targetIds.has(id)) {
            console.warn(`Cannot redo: recipe "${id}" is in execution order`)
            return prevIndex
          }
        }
        setRecipes(targetRecipes)
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

  const onPick = useCallback((p: string) => {
    setInputPath(p)
    pushRecent(p)
    setPickerOpen(false)
  }, [pushRecent])

  const onPickerClose = useCallback(() => setPickerOpen(false), [])

  const copyPath = async () => {
    try {
      await navigator.clipboard.writeText(inputPath)
    } catch {}
  }

  const runStream = useCallback(async () => {
    // Abort any previous stream before starting a new one (prevents
    // orphaned connections when the user rapidly clicks Run).
    abortControllerRef.current?.abort()
    setEvents([]); setGraph(null); setTrefoilData(null); setMolecularData(null); setQuantumData(null); setPhysicsData(null); setMathData(null); setRiscvData(null); setVerilogData(null); setFpgaData(null); setCipherData(null); setEcosystemData(null); setDocIngestData(null); setAutonomiData(null); setDataViz3D(null); setError(null)
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

    // Recursively expand recipes so allSkills contains only real skill names.
    const expandRecipeSkills = (recipeId: string, visited = new Set<string>()): string[] => {
      if (visited.has(recipeId)) return []
      visited.add(recipeId)
      const recipe = recipes.find((r) => r.id === recipeId)
      if (!recipe) return []
      const out: string[] = []
      for (const s of recipe.skills) {
        if (recipes.some((r) => r.id === s)) {
          out.push(...expandRecipeSkills(s, visited))
        } else {
          out.push(s)
        }
      }
      return out
    }
    const currentSkills = unifiedOrder
      .filter(i => i.type === 'skill')
      .map(i => i.content)
    const recipeSkills = unifiedOrder
      .filter(i => i.type === 'recipe')
      .flatMap((item) => expandRecipeSkills(item.content))
    const allSkills = [...new Set([...currentSkills, ...recipeSkills])]

    const body: { goal: string; skills: string[]; input_path?: string; metadata?: RunRequestMetadata; execution_order?: ExecutionOrderItem[]; use_hierarchical?: boolean } = { 
      goal, 
      skills: allSkills,
      execution_order: executionOrder,
      use_hierarchical: useHierarchical
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
    // Include recipe definitions so the backend can validate and expand
    // user-created recipes that aren't in the canonical DEFAULT_RECIPES.
    meta.recipe_definitions = recipes.map((r) => ({
      id: r.id,
      label: r.label,
      skills: r.skills,
      hint: r.hint,
    }))
    if (Object.keys(meta).length) body.metadata = meta

    // WebSocket transport path with auto-reconnect and resilience
    if (useWebSocket) {
      const WS_MAX_RETRIES = 3
      const WS_BASE_DELAY_MS = 1000
      let ws: WebSocket | null = null
      let retryCount = 0
      let heartbeatTimer: ReturnType<typeof setInterval> | null = null
      let abortCheckTimer: ReturnType<typeof setInterval> | null = null

      const cleanup = () => {
        if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
        if (abortCheckTimer) { clearInterval(abortCheckTimer); abortCheckTimer = null }
        if (ws) { try { ws.close() } catch {} ws = null }
        wsRef.current = null
      }

      const connect = async (): Promise<boolean> => {
        return new Promise((resolve) => {
          const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          const token = getLocalStorage()?.getItem('uar_api_key')
          const wsUrl = token ? `${proto}//${window.location.host}/ws/run?token=${encodeURIComponent(token)}` : `${proto}//${window.location.host}/ws/run`
          ws = new WebSocket(wsUrl)
          wsRef.current = ws
          setWsStatus(retryCount > 0 ? 'reconnecting' : 'connecting')

          const onOpen = () => {
            setWsStatus('open')
            retryCount = 0
            ws!.send(JSON.stringify(body))
            setStartTime(Date.now())

            // Heartbeat: detect stale server connections
            let lastPong = Date.now()
            heartbeatTimer = setInterval(() => {
              if (Date.now() - lastPong > 45000) {
                console.warn('WS heartbeat timeout, closing')
                ws?.close()
              }
            }, 20000)

            ws!.onmessage = (msg: MessageEvent) => {
              if (!wsRef.current) return
              lastPong = Date.now()
              if (eventCountRef.current >= MAX_EVENTS) {
                ws?.close()
                setError({ message: `Event limit reached (${MAX_EVENTS}).`, timestamp: Date.now() })
                setIsRunning(false)
                return
              }
              try {
                const json = JSON.parse(msg.data)
                // Skip heartbeat events from UI log to avoid noise
                if (json.type === 'heartbeat') return
                eventCountRef.current++
                setEvents((prev) => {
                  const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                  return [...next, json]
                })
                if (json.type === 'skill_start' && json.skill) setCurrentSkill(json.skill)
                if (json.type === 'skill_complete' && json.skill) {
                  setCurrentSkill(`Completed: ${json.skill}`)
                  if (json.skill === 'trefoil_simulation' && json.payload?.result) {
                    setTrefoilData(json.payload.result)
                  }
                  if (json.skill === 'molecular_visualization' && json.payload?.result) {
                    setMolecularData(json.payload.result)
                  }
                  if (json.skill === 'quantum_circuit_visualization' && json.payload?.result) {
                    setQuantumData(json.payload.result)
                  }
                  if (json.skill === 'physics_compute' && json.payload?.result) {
                    setPhysicsData(json.payload.result)
                  }
                  if (json.skill === 'math_compute' && json.payload?.result) {
                    setMathData(json.payload.result)
                  }
                  if (json.skill === 'riscv_sim' && json.payload?.result) {
                    setRiscvData(json.payload.result)
                  }
                  if (json.skill === 'verilog_parse' && json.payload?.result) {
                    setVerilogData(json.payload.result)
                  }
                  if (json.skill === 'fpga_verify' && json.payload?.result) {
                    setFpgaData(json.payload.result)
                  }
                  if (json.skill === 'cipher_ops' && json.payload?.result) {
                    setCipherData(json.payload.result)
                  }
                  if (json.skill === 'uor_ecosystem_status' && json.payload?.result) {
                    setEcosystemData(json.payload.result)
                  }
                  if (json.skill === 'doc_ingest' && json.payload?.result) {
                    setDocIngestData(json.payload.result)
                  }
                  if (json.skill === 'autonomi_status' && json.payload?.result) {
                    setAutonomiData(json.payload.result)
                  }
                  if (json.skill === 'data_viz_3d' && json.payload?.result) {
                    setDataViz3D(json.payload.result)
                  }
                  if (json.skill === 'math_plot' && json.payload?.result) {
                    setMathPlotData(json.payload.result)
                  }
                }
                if (json.type === 'recipe_start' && json.payload?.recipe_id) setCurrentSkill(`Recipe: ${json.payload.recipe_id}`)
                if (json.type === 'recipe_end' && json.payload?.recipe_id) setCurrentSkill(`Completed recipe: ${json.payload.recipe_id}`)
                if (json.type === 'orchestration_plan' && json.payload?.graph) setGraph(json.payload.graph)
                if (json.type === 'metrics' && json.payload) setMetrics(json.payload)
                if (json.type === 'error' && json.error) setError({ message: json.error, timestamp: Date.now() })
                if (json.type === 'skill_failed' && json.error) setError({ message: `${json.skill ? `[${json.skill}] ` : ''}${json.error}`, timestamp: Date.now() })
              } catch (parseError) {
                console.error('Failed to parse WebSocket message:', parseError, msg.data)
              }
            }

            // Abort handler
            abortCheckTimer = setInterval(() => {
              if (abortControllerRef.current?.signal.aborted) {
                cleanup()
              }
            }, 500)

            resolve(true)
          }

          const onError = () => {
            setWsStatus('error')
            resolve(false)
          }

          const onClose = () => {
            if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
            if (abortCheckTimer) { clearInterval(abortCheckTimer); abortCheckTimer = null }
            wsRef.current = null
            setWsStatus('closed')
            resolve(false)
          }

          ws.onopen = onOpen
          ws.onerror = onError
          ws.onclose = onClose

          // Connection timeout fallback
          setTimeout(() => {
            if (ws?.readyState !== WebSocket.OPEN) {
              resolve(false)
            }
          }, 10000)
        })
      }

      try {
        eventCountRef.current = 0
        while (retryCount <= WS_MAX_RETRIES) {
          const connected = await connect()
          if (connected) {
            // Wait for graceful close (execution done)
            await new Promise<void>((resolve) => {
              const checkDone = setInterval(() => {
                if (!ws || ws.readyState === WebSocket.CLOSED) {
                  clearInterval(checkDone)
                  resolve()
                }
              }, 200)
            })
            setIsRunning(false)
            setIsStopping(false)
            setWsStatus('idle')
            cleanup()
            return
          }

          retryCount++
          if (retryCount <= WS_MAX_RETRIES) {
            const delay = WS_BASE_DELAY_MS * Math.pow(2, retryCount - 1)
            console.log(`WS reconnecting in ${delay}ms (attempt ${retryCount}/${WS_MAX_RETRIES})`)
            await new Promise(r => setTimeout(r, delay))
          }
        }

        setError({ message: 'WebSocket failed after max retries', timestamp: Date.now() })
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          cleanup()
          return
        }
        setError({ message: err instanceof Error ? err.message : 'WebSocket error', timestamp: Date.now() })
      } finally {
        setIsRunning(false)
        setIsStopping(false)
        setWsStatus('idle')
        cleanup()
      }
      return
    }

    // Add timeout to abort controller
    const timeoutId = setTimeout(() => {
      abortControllerRef.current?.abort()
      setError({ message: 'Request timeout - server did not respond in time', timestamp: Date.now() })
      setIsRunning(false)
    }, 300000) // 5 minute timeout
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
    let decoder: TextDecoder | undefined

    try {
      setCurrentSkill(selectedSkills[0] || 'Starting')
      setStartTime(Date.now())
      const res = await fetch('/api/uar/stream', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      })
      // Clear timeout immediately after fetch completes to prevent race condition
      clearTimeout(timeoutId)

      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${res.statusText}${text ? ` — ${text}` : ''}`)
      }
      reader = res.body?.getReader()
      decoder = new TextDecoder()
      if (!reader) throw new Error('No response body reader available')

      let buffer = ''
      let lastEventTime = Date.now()
      const HEARTBEAT_INTERVAL = 30000 // 30 seconds
      const HEARTBEAT_ABORT_THRESHOLD = 2 // Abort after 2 missed heartbeats (60 seconds)

      heartbeatTimer = setInterval(() => {
        if (Date.now() - lastEventTime > HEARTBEAT_INTERVAL * HEARTBEAT_ABORT_THRESHOLD) {
          abortControllerRef.current?.abort()
          setError({ message: `Connection stalled - no events received for ${HEARTBEAT_INTERVAL * HEARTBEAT_ABORT_THRESHOLD / 1000}s`, timestamp: Date.now() })
          if (heartbeatTimer) {
            clearInterval(heartbeatTimer)
            heartbeatTimer = null
          }
        }
      }, HEARTBEAT_INTERVAL)

      while (true) {
        if (eventCountRef.current >= MAX_EVENTS) {
          abortControllerRef.current?.abort()
          break
        }
        const { done, value } = await reader.read()
        if (done) break
        if (abortControllerRef.current?.signal.aborted) break

        lastEventTime = Date.now()

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data:')) continue
            try {
              const json = JSON.parse(line.replace('data: ', ''))
              // Skip heartbeat events from UI log to avoid noise
              if (json.type === 'heartbeat') continue
              // Check event limit before processing to avoid processing events beyond limit
              if (eventCountRef.current >= MAX_EVENTS) {
                abortControllerRef.current?.abort()
                setError({ message: `Event limit reached (${MAX_EVENTS}).`, timestamp: Date.now() })
                setIsRunning(false)
                break
              }
              eventCountRef.current++
              setEvents((prev) => {
                const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                return [...next, json]
              })
              if (json.type === 'skill_start' && json.skill) setCurrentSkill(json.skill)
              if (json.type === 'skill_complete' && json.skill) {
                setCurrentSkill(`Completed: ${json.skill}`)
                if (json.skill === 'trefoil_simulation' && json.payload?.result) {
                  setTrefoilData(json.payload.result)
                }
                if (json.skill === 'molecular_visualization' && json.payload?.result) {
                  setMolecularData(json.payload.result)
                }
                if (json.skill === 'quantum_circuit_visualization' && json.payload?.result) {
                  setQuantumData(json.payload.result)
                }
                if (json.skill === 'physics_compute' && json.payload?.result) {
                  setPhysicsData(json.payload.result)
                }
                if (json.skill === 'math_compute' && json.payload?.result) {
                  setMathData(json.payload.result)
                }
                if (json.skill === 'riscv_sim' && json.payload?.result) {
                  setRiscvData(json.payload.result)
                }
                if (json.skill === 'verilog_parse' && json.payload?.result) {
                  setVerilogData(json.payload.result)
                }
                if (json.skill === 'fpga_verify' && json.payload?.result) {
                  setFpgaData(json.payload.result)
                }
                if (json.skill === 'cipher_ops' && json.payload?.result) {
                  setCipherData(json.payload.result)
                }
                if (json.skill === 'uor_ecosystem_status' && json.payload?.result) {
                  setEcosystemData(json.payload.result)
                }
                if (json.skill === 'doc_ingest' && json.payload?.result) {
                  setDocIngestData(json.payload.result)
                }
                if (json.skill === 'autonomi_status' && json.payload?.result) {
                  setAutonomiData(json.payload.result)
                }
                if (json.skill === 'data_viz_3d' && json.payload?.result) {
                  setDataViz3D(json.payload.result)
                }
              }
              if (json.type === 'recipe_start' && json.payload?.recipe_id) setCurrentSkill(`Recipe: ${json.payload.recipe_id}`)
              if (json.type === 'recipe_end' && json.payload?.recipe_id) setCurrentSkill(`Completed recipe: ${json.payload.recipe_id}`)
              if (json.type === 'orchestration_plan' && json.payload?.graph) setGraph(json.payload.graph)
              if (json.type === 'metrics' && json.payload) setMetrics(json.payload)
              if (json.run?.final_context?.dependency_map) setGraph(json.run.final_context.dependency_map)
              if (json.type === 'error' && json.error) setError({ message: json.error, timestamp: Date.now() })
              if (json.type === 'skill_failed' && json.error) setError({ message: `${json.skill ? `[${json.skill}] ` : ''}${json.error}`, timestamp: Date.now() })
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError, 'Data:', line)
              setError({ message: 'Failed to parse server response', timestamp: Date.now() })
            }
          }
          if (eventCountRef.current >= MAX_EVENTS) break
        }
      }
    } catch (err) {
      clearTimeout(timeoutId)
      if (err instanceof Error && err.name === 'AbortError') return
      setError({ message: err instanceof Error ? err.message : 'Unknown error occurred', timestamp: Date.now() })
    } finally {
      clearTimeout(timeoutId)
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      if (reader) try { reader.releaseLock() } catch {}
      setIsRunning(false)
      setIsStopping(false)
      if (!abortControllerRef.current?.signal.aborted) {
        abortControllerRef.current = null
      }
    }
  }, [goal, inputPath, unifiedOrder, recipes, backendSkills, graphragMethod, ollamaModel, autonomiKey, autonomiNetwork, autonomiPublic, autonomiAddress, pushRecent, useHierarchical])

  const stopStream = useCallback(() => {
    setIsStopping(true)
    abortControllerRef.current?.abort()
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  // Graph rendering is delegated to GraphVisualizer component

  const clearEvents = useCallback(() => { setEvents([]); setError(null); setMetrics(null); setTrefoilData(null); setMolecularData(null); setQuantumData(null); setPhysicsData(null); setMathData(null); setRiscvData(null); setVerilogData(null); setFpgaData(null); setCipherData(null); setEcosystemData(null); setDocIngestData(null); setAutonomiData(null); setDataViz3D(null); eventCountRef.current = 0 }, [])

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch('/api/uar/runs', { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setRunsHistory(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.warn('Failed to fetch runs history:', e)
    }
  }, [])

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
        onClose={onPickerClose}
        onPick={onPick}
      />

      <a href="#main-content" className={styles.skipLink}>Skip to main content</a>
      <div className={styles.header}>
        <h3 className={styles.headerTitle}>🤖 Universal Agent Runtime (UAR)</h3>
        <button
          onClick={() => setDarkMode(!darkMode)}
          className={styles.skillGuideButton}
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        <button
          onClick={() => setShowHelp(!showHelp)}
          className={styles.skillGuideButton}
          title="Toggle quick start tips"
          aria-label="Toggle quick start tips"
          aria-pressed={showHelp}
        >
          💡
        </button>
        <button
          onClick={() => setSkillGuideOpen(true)}
          className={styles.skillGuideButton}
          title="View detailed skill documentation"
          aria-label="View detailed skill documentation"
        >
          📘
        </button>
        <span className={styles.projectRoot}>UOR Support <a href="https://uor.foundation" target="_blank" rel="noopener noreferrer">{uorImageError ? <span className={styles.uorFallbackIcon}>🔗</span> : <img src="https://uor.foundation/assets/uor-icon-new-CQuNVmtH.png" alt="UOR" width="20" height="20" onError={() => setUorImageError(true)} />}</a></span>
      </div>

      <main id="main-content" className={styles.mainContent}>
      {showHelp && (
        <div className={styles.helpBox}>
          <div className={styles.helpSection}>
            <strong>Quick Start:</strong>
            <ul className={styles.helpList}>
              <li>1. <strong>Select documents</strong> from the library or upload files</li>
              <li>2. <strong>Set a goal</strong> describing what you want to accomplish</li>
              <li>3. <strong>Build your order</strong> - add skills and recipes to the unified list, drag-and-drop to reorder</li>
              <li>4. <strong>Run</strong> and watch real-time events, 3D visualizers, and dependency graphs appear</li>
            </ul>
          </div>
          <div className={styles.helpSection}>
            <strong>Pro Tips:</strong>
            <ul className={styles.helpList}>
              <li><strong>Unified Order</strong>: Mix skills and recipes freely - each gets a unique color and ID</li>
              <li><strong>Duplicate</strong> items to repeat a skill without rebuilding the whole sequence</li>
              <li><strong>Recipes</strong> (🍳) encapsulate workflows - create your own in the Recipe Builder</li>
              <li><strong>3D Visualizers</strong> auto-appear when skills produce data - click 🎥 to record video</li>
              <li><strong>WebSocket mode</strong> is more resilient for long runs than default SSE</li>
              <li><strong>Hierarchical mode</strong> runs recipes as discrete units with retry per recipe block</li>
              <li>Hover over skills for descriptions; click 💡 per section for detailed tips</li>
            </ul>
          </div>
        </div>
      )}

      {error && (
        <div className={styles.errorBox} role="alert" aria-live="assertive">
          <strong>Error:</strong> {error.message}
          {error.code && <span className={styles.errorCode}>[{error.code}]</span>}
          {error.requestId && <span className={styles.errorCode}>req: {error.requestId}</span>}
          <button onClick={() => setError(null)} className={styles.dismissButton} aria-label="Dismiss error">Dismiss</button>
          <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(error, null, 2)).catch(() => {}) }} className={styles.copyButton} aria-label="Copy error details to clipboard">Copy</button>
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
            onClick={() => {
              setTipsTargetSection('Documents')
              setTipsPopupOpen(true)
            }}
            className={styles.skillGuideButton}
            title="View tips"
            aria-label="View document tips"
          >
            💡
          </button>
          <button
            onClick={() => setPickerOpen(true)}
            disabled={isRunning}
            className={styles.pickButton}
            title="Open file picker"
            aria-label="Open file picker"
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
                <button onClick={refreshLibrary} className={styles.refreshButton} title="Refresh library list" aria-label="Refresh library list">↻</button>
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
                      <span className={styles.libraryItemName} onClick={() => onPick(f.path)} onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onPick(f.path) } }} tabIndex={0} role="button" title={f.path} aria-label={`Select file ${f.name}`}>
                        📄 {f.name}
                      </span>
                      <span className={styles.libraryItemSize}>{human(f.size)}</span>
                      <button onClick={() => deleteLibFile(f.name)} disabled={isRunning} className={styles.deleteButton} title="Delete" aria-label={`Delete file ${f.name}`}>✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className={styles.presetsContainer}>
              <div className={styles.label} title="Quick access to pre-configured project directories">Presets</div>
              {!presetsLoaded && <span className={styles.loadingText}>(loading…)</span>}
              {presetsLoaded && presets.length === 0 && <span className={styles.loadingText}>(none)</span>}
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
                <button onClick={copyPath} disabled={!inputPath} className={styles.iconButton} title="Copy path to clipboard" aria-label="Copy path to clipboard">📋</button>
                <button onClick={() => setInputPath('')} disabled={!inputPath || isRunning} className={styles.iconButton} title="Clear input path" aria-label="Clear input path">✕</button>
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
              onClick={() => {
                setTipsTargetSection('Goal')
                setTipsPopupOpen(true)
              }}
              className={styles.skillGuideButton}
              title="View tips"
              aria-label="View goal tips"
            >
              💡
            </button>
          </label>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.goalInputRow}>
                <input
                  value={goal}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGoal(e.target.value)}
                  onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                    if (e.key === 'Enter' && canRun) {
                      e.preventDefault()
                      runStream()
                    }
                  }}
                  placeholder="What do you want to accomplish?"
                  disabled={isRunning}
                  className={`${styles.input} ${styles.widthFull}`}
                />
                <button
                  onClick={runStream}
                  disabled={!canRun}
                  className={styles.goalSubmitButton}
                  title={isRunning ? 'Currently running' : 'Execute selected skills'}
                  aria-label="Run"
                >
                  {isRunning ? '⏳' : '▶'}
                </button>
              </div>
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
              onClick={() => {
                setTipsTargetSection('Skills')
                setTipsPopupOpen(true)
              }}
              className={styles.skillGuideButton}
              title="View tips"
              aria-label="View skills tips"
            >
              💡
            </button>
            <button onClick={() => toggleAllGroups(false)} className={styles.collapseAllButton} disabled={isRunning} title="Collapse all" aria-label="Collapse all skill groups">
              ▼
            </button>
            <button onClick={() => toggleAllGroups(true)} className={styles.collapseAllButton} disabled={isRunning} title="Expand all" aria-label="Expand all skill groups">
              ▲
            </button>
            <button onClick={() => {
              setUnifiedOrder((prev) => {
                const newOrder = prev.filter(i => i.type !== 'skill')
                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                setSkillHistory((history) => [...history.slice(0, skillHistoryIndexRef.current + 1), newSkills])
                setSkillHistoryIndex((prev) => prev + 1)
                setUnifiedOrderHistory((history) => [...history.slice(0, unifiedOrderHistoryIndexRef.current + 1), newOrder])
                setUnifiedOrderHistoryIndex((prev) => prev + 1)
                setSkillLastPositions({})
                return newOrder
              })
            }} className={styles.collapseAllButton} disabled={isRunning} title="Clear all selected skills" aria-label="Clear all selected skills">
              ✕
            </button>
            <button onClick={undoSkills} className={styles.collapseAllButton} disabled={isRunning || skillHistoryIndex === 0} title="Undo" aria-label="Undo skill selection">
              ↶
            </button>
            <button onClick={redoSkills} className={styles.collapseAllButton} disabled={isRunning || skillHistoryIndex === skillHistory.length - 1} title="Redo" aria-label="Redo skill selection">
              ↷
            </button>
          </label>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.skillSearchWrap}>
                <input
                  type="text"
                  value={skillSearch}
                  onChange={(e) => setSkillSearch(e.target.value)}
                  placeholder="Search skills…"
                  className={styles.skillSearchInput}
                  aria-label="Search skills"
                />
                {skillSearch && (
                  <button
                    onClick={() => setSkillSearch('')}
                    className={styles.skillSearchClear}
                    aria-label="Clear search"
                  >
                    ✕
                  </button>
                )}
              </div>
              <div className={styles.skillsContainer}>
                {(() => {
                  const query = skillSearch.trim().toLowerCase()
                  const groups = query
                    ? SKILL_GROUPS.map(g => ({
                        ...g,
                        skills: g.skills.filter(s =>
                          s.label.toLowerCase().includes(query) ||
                          s.desc.toLowerCase().includes(query)
                        )
                      })).filter(g => g.skills.length > 0)
                    : SKILL_GROUPS
                  return groups.map((group) => {
                    const isCollapsed = collapsedGroups[group.name]
                    return (
                      <div key={group.name} className={styles.skillGroup}>
                        <div className={styles.skillGroupHeader} onClick={() => toggleGroup(group.name)} onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleGroup(group.name) } }} tabIndex={0} role="button" aria-expanded={!isCollapsed} title={`Click to ${isCollapsed ? 'expand' : 'collapse'} ${group.name} skills`}>
                          <span className={styles.skillGroupIcon}>{group.icon}</span>
                          <span className={styles.skillGroupName}>{group.name}</span>
                          <span className={styles.collapseIcon}>{isCollapsed ? '▶' : '▼'}</span>
                        </div>
                        {!isCollapsed && (
                          <div className={styles.skillGroupSkills}>
                            {group.skills.map((s) => {
                              const count = unifiedOrder.filter(i => i.type === 'skill' && i.content === s.id).length
                              return (
                                <button key={s.id} onClick={() => addSkill(s.id)} disabled={isRunning} title={s.desc} className={chip(count > 0, isRunning)}>
                                  {count > 0 ? `✓ (${count}) ` : ''}{s.label}
                                </button>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })
                })()}
              </div>
              <div className={styles.orderText} title="Skills execute in this order">
                <strong>Order of Operation:</strong>
                {unifiedOrder.length > 0 && (
                  <button
                    onClick={() => {
                      setUnifiedOrder([])
                      setUnifiedOrderHistory([[]])
                      setUnifiedOrderHistoryIndex(0)
                      setSkillLastPositions({})
                      setSkillHistory([[]])
                      setSkillHistoryIndex(0)
                    }}
                    className={styles.clearButton}
                    disabled={isRunning}
                    title="Clear execution order"
                  >
                    ✕
                  </button>
                )}
                {unifiedOrder.length === 0 ? (
                  <span>(none)</span>
                ) : (
                  <div className={styles.orderChips}>
                    {unifiedOrder.map((item, index) => {
                      const hash = item.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
                      const colorClass = `color-${hash % 10}`
                      const label = item.type === 'skill' ? item.content : recipes.find(r => r.id === item.content)?.label || item.content
                      return (
                        <div
                          key={item.id}
                          className={`${styles.orderChip} ${styles[colorClass]}`}
                          draggable={!isRunning}
                          aria-label={`${item.type === 'recipe' ? 'Recipe' : 'Skill'}: ${label} (position ${index + 1})`}
                          onDragStart={(e) => {
                            e.dataTransfer.setData('text/uar-order', item.id)
                            e.dataTransfer.effectAllowed = 'move'
                          }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault()
                            if (!Array.from(e.dataTransfer.types).includes('text/uar-order')) return
                            const fromId = e.dataTransfer.getData('text/uar-order')
                            const toIndex = index
                            setUnifiedOrder((prev) => {
                              const fromIndex = prev.findIndex((i) => i.id === fromId)
                              if (fromIndex === -1 || fromIndex === toIndex) return prev
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
                              const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                              setSkillHistory((history) => {
                                const newHistory = [...history.slice(0, skillHistoryIndexRef.current + 1), newSkills]
                                setSkillHistoryIndex((idx) => idx + 1)
                                return newHistory
                              })
                              setUnifiedOrderHistory((history) => {
                                const newHistory = [...history.slice(0, unifiedOrderHistoryRef.current + 1), newOrder]
                                setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                return newHistory
                              })
                              return newOrder
                            })
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
                                setSkillLastPositions((prevPositions) => {
                                  const newPositions = { ...prevPositions }
                                  for (let i = index + 1; i < newOrder.length; i++) {
                                    if (newOrder[i].type === 'skill') {
                                      newPositions[newOrder[i].content] = i
                                    }
                                  }
                                  return newPositions
                                })
                                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                                setSkillHistory((history) => {
                                  const newHistory = [...history.slice(0, skillHistoryIndexRef.current + 1), newSkills]
                                  setSkillHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                setUnifiedOrderHistory((history) => {
                                  const newHistory = [...history.slice(0, unifiedOrderHistoryIndexRef.current + 1), newOrder]
                                  setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                return newOrder
                              })
                            }}
                            className={styles.orderChipAction}
                            disabled={isRunning}
                            title={`Duplicate ${label}`}
                            aria-label={`Duplicate ${label}`}
                          >
                            +
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setUnifiedOrder((prev) => {
                                const newOrder = prev.filter((_, i) => i !== index)
                                setSkillLastPositions((prevPositions) => {
                                  const newPositions = { ...prevPositions }
                                  for (let i = index; i < newOrder.length; i++) {
                                    if (newOrder[i].type === 'skill') {
                                      newPositions[newOrder[i].content] = i
                                    }
                                  }
                                  return newPositions
                                })
                                const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                                setSkillHistory((history) => {
                                  const newHistory = [...history.slice(0, skillHistoryIndexRef.current + 1), newSkills]
                                  setSkillHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                setUnifiedOrderHistory((history) => {
                                  const newHistory = [...history.slice(0, unifiedOrderHistoryIndexRef.current + 1), newOrder]
                                  setUnifiedOrderHistoryIndex((idx) => idx + 1)
                                  return newHistory
                                })
                                return newOrder
                              })
                            }}
                            className={styles.orderChipAction}
                            disabled={isRunning}
                            title={`Remove ${label}`}
                            aria-label={`Remove ${label}`}
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
                  <strong>Recipes</strong>
                  <button
                    onClick={() => setRecipesPopupOpen(true)}
                    className={styles.libraryLink}
                    title="View recipes library"
                    aria-label="View recipes library"
                  >
                    📚
                  </button>
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
                        e.dataTransfer.setData('text/uar-recipe', r.id)
                        e.dataTransfer.effectAllowed = 'move'
                      }}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault()
                        if (!Array.from(e.dataTransfer.types).includes('text/uar-recipe')) return
                        const fromId = e.dataTransfer.getData('text/uar-recipe')
                        setRecipes((prev) => {
                          const fromIndex = prev.findIndex((recipe) => recipe.id === fromId)
                          const toIndex = index
                          if (fromIndex === -1 || fromIndex === toIndex) return prev
                          const newRecipes = [...prev]
                          const [moved] = newRecipes.splice(fromIndex, 1)
                          newRecipes.splice(toIndex, 0, moved)
                          // Update history atomically
                          setRecipeHistory((history) => {
                            const newHistory = [...history.slice(0, recipeHistoryIndexRef.current + 1), newRecipes]
                            setRecipeHistoryIndex((idx) => idx + 1)
                            return newHistory
                          })
                          return newRecipes
                        })
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
                            const newSkills = newOrder.filter(i => i.type === 'skill').map(i => i.content)
                            setSkillHistory((history) => [...history.slice(0, skillHistoryIndexRef.current + 1), newSkills])
                            setSkillHistoryIndex((idx) => idx + 1)
                            setUnifiedOrderHistory((history) => {
                              const newHistory = [...history.slice(0, unifiedOrderHistoryIndexRef.current + 1), newOrder]
                              setUnifiedOrderHistoryIndex((idx) => idx + 1)
                              return newHistory
                            })
                            return newOrder
                          })
                        }}
                        className={`${styles.presetButton} ${unifiedOrder.some(i => i.type === 'recipe' && i.content === r.id) ? styles.chipActive : ''}`}
                      >
                        {(() => {
                          const count = unifiedOrder.filter(i => i.type === 'recipe' && i.content === r.id).length
                          return count > 0 ? `✓ (${count}) ` : ''
                        })()}{r.label}
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
                      <select value={graphragMethod} onChange={(e) => setGraphragMethod(e.target.value as 'local' | 'global')} className={styles.advancedOverrideSelect}>
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
                        <select value={autonomiNetwork} onChange={(e) => setAutonomiNetwork(e.target.value as 'testnet' | 'mainnet')} className={styles.advancedOverrideSelect}>
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

              {/* User Presets */}
              <div className={styles.advancedOverrides}>
                <label className={`${styles.label} ${styles.marginBottom6}`} title="Save and restore complete panel configurations">User Presets</label>
                <div className={styles.advancedOverridesContainer}>
                  <div className={styles.advancedOverride}>
                    <input
                      value={userPresetName}
                      onChange={(e) => setUserPresetName(e.target.value)}
                      placeholder="Preset name…"
                      className={styles.advancedOverrideInput}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveUserPreset() } }}
                    />
                    <button onClick={saveUserPreset} disabled={!userPresetName.trim()} className={styles.smallButton} title="Save current configuration">
                      💾 Save
                    </button>
                  </div>
                  {userPresets.length > 0 && (
                    <div className={styles.presetsContainerCompact}>
                      {userPresets.map((p) => (
                        <div key={p.name} className={styles.presetRow}>
                          <button
                            onClick={() => loadUserPreset(p)}
                            className={styles.chip}
                            title={`Load: ${p.goal.slice(0, 40)}${p.goal.length > 40 ? '…' : ''} · ${p.unifiedOrder.length} items`}
                          >
                            {p.name}
                          </button>
                          <button
                            onClick={() => { if (confirm(`Delete preset "${p.name}"?`)) deleteUserPreset(p.name) }}
                            className={styles.deleteButton}
                            title="Delete preset"
                            aria-label={`Delete preset ${p.name}`}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
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
            onClick={() => {
              setTipsTargetSection('Run')
              setTipsPopupOpen(true)
            }}
            className={styles.skillGuideButton}
            title="View tips"
            aria-label="View run tips"
          >
            💡
          </button>
        </div>
        <div className={styles.presetsContainer}>
          <button
            onClick={() => setUseWebSocket((v) => !v)}
            disabled={isRunning}
            className={`${styles.runButton} ${styles.smallButton}`}
            title={useWebSocket ? 'Using WebSocket transport' : 'Using SSE transport (click to switch)'}
            aria-label={useWebSocket ? 'Switch to SSE transport' : 'Switch to WebSocket transport'}
            aria-pressed={useWebSocket}
          >
            {useWebSocket ? '⚡ WS' : '⬡ SSE'}
          </button>
          <button
            onClick={() => setUseHierarchical((v) => !v)}
            disabled={isRunning}
            className={`${styles.runButton} ${styles.smallButton}`}
            title={
              useHierarchical
                ? 'Hierarchical execution: recipes run as discrete units with snapshot/retry/params scoping'
                : 'Flat execution: recipes expand into a single skill list (click to switch)'
            }
            aria-label={useHierarchical ? 'Switch to flat execution' : 'Switch to hierarchical execution'}
            aria-pressed={useHierarchical}
          >
            {useHierarchical ? '🔀 Nested' : '➡ Flat'}
          </button>
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
            <span className={styles.runStatus} aria-live="polite" aria-atomic="true">
              {isStopping ? 'Stopping' : currentSkill} • {Math.floor((Date.now() - startTime) / 1000)}s
              {useWebSocket && wsStatus !== 'idle' && wsStatus !== 'open' && (
                <span className={styles.wsStatusSuffix}>
                  ({wsStatus})
                </span>
              )}
            </span>
          )}
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className={`${styles.createFolderInput} ${styles.eventFilterSelect}`}
            title="Filter events by type"
            aria-label="Filter events by type"
          >
            <option value="all">All Events</option>
            <option value="recipe">Recipe Boundaries</option>
            <option value="skill">Skill Events</option>
            <option value="error">Errors Only</option>
          </select>
          <button
            onClick={() => { fetchRuns(); setShowRunsPanel(true) }}
            className={styles.clearEventsButton}
            title="View past runs"
          >
            Runs
          </button>
          <button
            onClick={() => setShowHealthDashboard(v => !v)}
            className={styles.clearEventsButton}
            title="Toggle health dashboard"
          >
            {showHealthDashboard ? 'Hide Health' : 'Health'}
          </button>
          <button onClick={clearEvents} className={styles.clearEventsButton} title="Clear event history from display">
            Clear Events
          </button>
        </div>
        {metrics && !isRunning && (
          <div className={styles.metricsPanel} title="Execution metrics from last run">
            <MetricsDashboard metrics={metrics} darkMode={darkMode} />
          </div>
        )}
        {showHealthDashboard && (
          <HealthDashboard />
        )}
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
              <div key={d.path || d.name || `doc-${i}`} className={styles.ingestedItem}>
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
          <div className={styles.timelineViewToggle}>
            <button
              onClick={() => setEventViewMode('timeline')}
              className={`${styles.timelineViewButton} ${eventViewMode === 'timeline' ? styles.timelineViewButtonActive : ''}`}
              title="Timeline view"
            >
              Timeline
            </button>
            <button
              onClick={() => setEventViewMode('json')}
              className={`${styles.timelineViewButton} ${eventViewMode === 'json' ? styles.timelineViewButtonActive : ''}`}
              title="Raw JSON view"
            >
              JSON
            </button>
          </div>
          <button
            onClick={() => {
              setTipsTargetSection('Events')
              setTipsPopupOpen(true)
            }}
            className={styles.skillGuideButton}
            title="View tips"
            aria-label="View events tips"
          >
            💡
          </button>
          {events.length > 0 && (
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(events, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = 'events.json'
                a.click()
                URL.revokeObjectURL(url)
              }}
              className={styles.skillGuideButton}
              title="Download all events as JSON"
              aria-label="Download all events as JSON"
            >
              📥
            </button>
          )}
        </div>
        <div className={styles.sectionWithTips}>
          <div className={styles.sectionContent}>
            <div className={styles.eventsContainer}>
              {(() => {
                const filtered = events.filter((e) => {
                  if (eventFilter === 'all') return true
                  if (eventFilter === 'recipe') {
                    return e?.type === 'recipe_start' || e?.type === 'recipe_end'
                  }
                  if (eventFilter === 'skill') {
                    return e?.type?.startsWith('skill_') || e?.type === 'parallel_start' || e?.type === 'parallel_complete'
                  }
                  if (eventFilter === 'error') {
                    return e?.type === 'error' || e?.type === 'skill_failed'
                  }
                  return true
                })
                return eventViewMode === 'json' ? (
                  <pre className={styles.eventsPre}>
                    {filtered.slice(-50).map((e, i) => {
                      const isRecipeEvent = e?.type === 'recipe_start' || e?.type === 'recipe_end'
                      const recipeClass = e?.type === 'recipe_start'
                        ? styles.recipeStart
                        : e?.type === 'recipe_end'
                          ? styles.recipeEnd
                          : ''
                      return (
                        <span
                          key={i}
                          className={isRecipeEvent ? `${styles.recipeEvent} ${recipeClass}` : ''}
                        >
                          {JSON.stringify(e, null, 2)}
                          {i < filtered.slice(-50).length - 1 ? '\n' : ''}
                        </span>
                      )
                    })}
                  </pre>
                ) : (
                  <RecipeTimeline events={filtered} recipes={recipes} />
                )
              })()}
            </div>
          </div>
        </div>
      </div>

      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong title="Visualizes dependencies and relationships">Dependency Graph</strong>
          <button
            onClick={() => {
              setTipsTargetSection('Graph')
              setTipsPopupOpen(true)
            }}
            className={styles.skillGuideButton}
            title="View tips"
            aria-label="View graph tips"
          >
            💡
          </button>
          {graph && (
            <button
              onClick={() => {
                const data = JSON.stringify(graph, null, 2)
                const blob = new Blob([data], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = 'dependency-graph.json'
                a.click()
                URL.revokeObjectURL(url)
              }}
              className={styles.skillGuideButton}
              title="Export graph as JSON"
            >
              📥
            </button>
          )}
        </div>
        <div className={styles.sectionWithTips}>
          <div className={styles.sectionContent}>
            <div className={styles.graphContainer}>
              <Suspense fallback={<div className={styles.loadingFallback}>Loading graph...</div>}>
                <GraphVisualizer graph={graph} darkMode={darkMode} />
              </Suspense>
            </div>
          </div>
        </div>
      </div>

      {/* 3D Trefoil Visualization */}
      {(trefoilData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🌀 3D Trefoil Simulation</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading 3D simulation...</div>}>
                  <TrefoilKnotVisualizer data={trefoilData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Molecular Visualization */}
      {(molecularData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🧬 Molecular Structure</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading molecule...</div>}>
                  <MolecularVisualizer data={molecularData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quantum Circuit Visualization */}
      {(quantumData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>⚛️ Quantum Circuit</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading quantum circuit...</div>}>
                  <QuantumCircuitVisualizer data={quantumData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Physics Computation */}
      {(physicsData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🔭 Physics Computation</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading physics results...</div>}>
                  <PhysicsVisualizer data={physicsData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Math Computation */}
      {(mathData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>📐 Math Computation</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading math results...</div>}>
                  <MathVisualizer data={mathData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Math Plot */}
      {(mathPlotData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>📊 Math Plot</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading plot...</div>}>
                  <MathPlotVisualizer data={mathPlotData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* RISC-V Simulation */}
      {(riscvData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🖥️ RISC-V Simulation</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading RISC-V simulation...</div>}>
                  <RiscvVisualizer data={riscvData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Verilog Parse */}
      {(verilogData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🔌 Verilog HDL</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading Verilog...</div>}>
                  <VerilogVisualizer data={verilogData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* FPGA Verification */}
      {(fpgaData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>⚡ FPGA Verification</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading FPGA results...</div>}>
                  <FpgaVisualizer data={fpgaData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cipher Operations */}
      {(cipherData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🔐 Crypto Operations</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading crypto results...</div>}>
                  <CipherDashboard data={cipherData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* UOR Ecosystem Status */}
      {(ecosystemData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🌐 Ecosystem Status</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading ecosystem status...</div>}>
                  <EcosystemDashboard data={ecosystemData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Document Ingest */}
      {(docIngestData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>📄 Document Ingest</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading document list...</div>}>
                  <DocIngestDashboard data={docIngestData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Autonomi Storage */}
      {(autonomiData || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>☁️ Autonomi Storage</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading Autonomi status...</div>}>
                  <AutonomiDashboard data={autonomiData} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3D Data Visualization */}
      {(dataViz3D || isRunning) && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h3>🧊 3D Mesh Visualization</h3>
          </div>
          <div className={styles.sectionWithTips}>
            <div className={styles.sectionContent}>
              <div className={styles.graphContainer}>
                <Suspense fallback={<div className={styles.loadingFallback}>Loading 3D mesh...</div>}>
                  <DataViz3D data={dataViz3D} darkMode={darkMode} />
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      )}

      {skillGuideOpen && (
        <div
          onClick={() => setSkillGuideOpen(false)}
          className={styles.skillGuideModalOverlay}
          role="presentation"
        >
          <div
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
            className={styles.skillGuideModalContent}
            role="dialog"
            aria-modal="true"
            aria-label="Skill Guide"
          >
            <div className={styles.skillGuideModalHeader}>
              <strong id="skill-guide-title">Skill Guide</strong>
              <button
                onClick={() => setSkillGuideOpen(false)}
                className={styles.modalCloseButton}
                aria-label="Close skill guide"
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
        <div ref={tipsPopupRef} className={styles.tipsPopup} role="dialog" aria-modal="true" aria-label="Tips">
          <div className={styles.tipsPopupHeader}>
            <span className={styles.tipsPopupTitle}>Tips</span>
            <button
              onClick={() => setTipsPopupOpen(false)}
              className={styles.tipsPopupClose}
              aria-label="Close tips"
            >
              ✕
            </button>
          </div>

          {/* Documents Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Documents')}
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Documents') } }}
              title="Click to expand/collapse Documents tips"
              data-section="Documents"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Documents']}
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
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Goal') } }}
              title="Click to expand/collapse Goal tips"
              data-section="Goal"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Goal']}
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
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Skills') } }}
              title="Click to expand/collapse Skills tips"
              data-section="Skills"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Skills']}
            >
              <span className={styles.tipsPopupSectionTitle}>Skills</span>
              <span>{expandedTipSections['Skills'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Skills'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Unified Order</strong>: Skills and recipes are combined in a single ordered list - drag-and-drop to reorder, mix skills and recipes freely</li>
                  <li><strong>Multiple instances</strong>: Add the same skill multiple times - each gets a unique color and ID for easy tracking</li>
                  <li><strong>Recipes</strong> (🍳 prefix) expand into their skills at runtime but appear as single units in the order - great for encapsulating workflows</li>
                  <li><strong>Duplicate / Remove</strong>: Use the buttons on each order item to clone or remove without breaking the sequence</li>
                  <li><strong>Skill order matters</strong>: By default skills execute sequentially, with each receiving the output of previous skills. Enable <strong>hierarchical mode</strong> for discrete recipe units with snapshot/retry</li>
                  <li><strong>Parallel execution</strong>: Groups of independent skills run in parallel automatically - the executor handles grouping</li>
                  <li><strong>AI/LLM skills</strong> require API keys (set in environment) or local services (Ollama, LM Studio must be running)</li>
                  <li><strong>Advanced options</strong> appear dynamically when relevant skills are selected (e.g., GraphRAG method, Ollama model)</li>
                  <li><strong>Skill dependencies</strong>: Some skills require specific outputs from earlier skills (e.g., graphrag_query needs graphrag_index first)</li>
                  <li><strong>Hover over skills</strong> to see descriptions of what each skill does</li>
                  <li><strong>Collapse/expand groups</strong> to focus on specific skill categories</li>
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
                onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection(group.name) } }}
                title={`Click to expand/collapse ${group.name} tips`}
                data-section={group.name}
                tabIndex={0}
                role="button"
                aria-expanded={expandedTipSections[group.name]}
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
                    {group.name === 'Multi-Agent' && (
                      <>
                        <li><strong>agent_workflow</strong>: Multi-agent workflows with Microsoft Agent Framework patterns - orchestrate multiple AI agents with defined roles</li>
                        <li><strong>crewai_task</strong>: Role-based agent tasks with CrewAI - research, analysis, writing, code review patterns</li>
                        <li><strong>crewai_workflow</strong>: Standard multi-agent workflows - research-analyze-write, code-review, data-analysis pipelines</li>
                        <li><strong>Requirements</strong>: autogen for agent_workflow, crewai for crewai tasks</li>
                        <li><strong>Use cases</strong>: Complex tasks requiring multiple specialized agents, collaborative AI workflows</li>
                        <li><strong>Workflow</strong>: Define goal, select agent pattern, agents execute in sequence with shared context</li>
                      </>
                    )}
                    {group.name === 'Advanced RAG' && (
                      <>
                        <li><strong>llamaindex_rag</strong>: Advanced RAG with LlamaIndex - hierarchical chunking, hybrid search, knowledge graph integration</li>
                        <li><strong>llamaindex_query</strong>: Query existing LlamaIndex RAG with multiple retrieval strategies - semantic, keyword, hybrid</li>
                        <li><strong>Requirements</strong>: llama-index package, documents ingested for indexing</li>
                        <li><strong>Use cases</strong>: Complex document Q&A, knowledge bases, research assistant, technical documentation search</li>
                        <li><strong>Workflow</strong>: Ingest documents, build index with llamaindex_rag, then query with llamaindex_query</li>
                        <li><strong>Comparison</strong>: LlamaIndex offers more advanced retrieval than basic GraphRAG - use for sophisticated document search</li>
                      </>
                    )}
                    {group.name === 'Pipeline Orchestration' && (
                      <>
                        <li><strong>dagster_pipeline</strong>: Execute Dagster pipelines with asset-based orchestration - data-aware scheduling and dependencies</li>
                        <li><strong>dagster_status</strong>: Check Dagster pipeline and asset status - monitor runs, materializations, and health</li>
                        <li><strong>Requirements</strong>: dagster package, Dagster instance running</li>
                        <li><strong>Use cases</strong>: Data pipeline orchestration, ML pipeline management, ETL workflow scheduling</li>
                        <li><strong>Workflow</strong>: Define assets and dependencies in Dagster, then trigger and monitor via UAR</li>
                      </>
                    )}
                    {group.name === 'Governance' && (
                      <>
                        <li><strong>guardrail_check</strong>: Check guardrails for agent outputs - content safety, rate limits, budget compliance</li>
                        <li><strong>budget_status</strong>: Check agent budget status - tokens used, API calls, cost, time limits</li>
                        <li><strong>blackboard_status</strong>: Check shared blackboard status for inter-agent coordination and message passing</li>
                        <li><strong>Requirements</strong>: guardrails-ai for guardrail_check</li>
                        <li><strong>Use cases</strong>: Content moderation, cost control, multi-agent coordination, compliance monitoring</li>
                        <li><strong>Workflow</strong>: Run governance checks before or after agent execution to ensure compliance</li>
                      </>
                    )}
                    {group.name === 'UOR Ecosystem' && (
                      <>
                        <li><strong>uor_addr_canonicalize</strong>: Canonicalize data per UOR-ADDR-1 spec and compute SHA-256 digest</li>
                        <li><strong>uor_addr_resolve</strong>: Resolve a UOR digest from the integrator object cache</li>
                        <li><strong>hologram_query</strong>: Submit geometric inference to gethologram.ai (requires HOLOGRAM_API_KEY)</li>
                        <li><strong>hologram_status</strong>: Check gethologram.ai service health</li>
                        <li><strong>moltbook_list</strong>: List recent topics from moltbook.com/m/uor forum</li>
                        <li><strong>moltbook_search</strong>: Search moltbook forum posts</li>
                        <li><strong>moltbook_post</strong>: Post a new topic to moltbook forum (requires MOLTBOOK_API_KEY)</li>
                        <li><strong>prism_btc_anchor</strong>: Anchor a UOR digest on Bitcoin (placeholder - pending public API)</li>
                        <li><strong>severance_infer</strong>: Run inference via Severance AI (placeholder - pending public API)</li>
                        <li><strong>anunix_health</strong>: Check Anunix host health (placeholder - pending public API)</li>
                        <li><strong>uor_ecosystem_status</strong>: Check status of all UOR ecosystem integrations at once</li>
                        <li><strong>Use cases</strong>: UOR data canonicalization, holographic inference, community forum integration, Bitcoin anchoring</li>
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
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Run') } }}
              title="Click to expand/collapse Run tips"
              data-section="Run"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Run']}
            >
              <span className={styles.tipsPopupSectionTitle}>Run</span>
              <span>{expandedTipSections['Run'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Run'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Run Stream</strong> executes the unified order with real-time event updates via SSE or WebSocket</li>
                  <li><strong>WebSocket toggle</strong>: Switch between SSE (default) and WebSocket for streaming - WebSocket includes auto-reconnect and heartbeat resilience</li>
                  <li><strong>Hierarchical mode</strong>: Enable for discrete recipe execution with snapshot/retry per recipe block instead of flat expansion</li>
                  <li><strong>Stop button</strong> appears during execution to abort the current run - works for both SSE and WebSocket transports</li>
                  <li><strong>Clear Events</strong> removes previous run data from the display - doesn't affect the server, just the UI</li>
                  <li><strong>Status bar</strong> shows running state, event count, and current skill/recipe at a glance</li>
                  <li><strong>3D Visualizers</strong>: When skills produce 3D data (molecular, quantum circuit, trefoil, mesh), interactive panels appear automatically with 🎥 video recording and 📷 PNG export</li>
                  <li><strong>Graph panel</strong>: Dependency graphs appear when dependency_map or GraphRAG skills emit graph data</li>
                  <li><strong>Prerequisites</strong>: Goal must be non-empty and at least one skill or recipe must be selected</li>
                  <li><strong>Event limit</strong>: System stops after 1000 events to prevent memory issues</li>
                  <li><strong>Error handling</strong>: Errors are displayed in the error banner with details, copy-to-clipboard, and dismiss</li>
                  <li><strong>Concurrency</strong>: Only one run at a time - the Run button is disabled while another is in progress</li>
                </ul>
              </div>
            )}
          </div>

          {/* Events Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Events')}
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Events') } }}
              title="Click to expand/collapse Events tips"
              data-section="Events"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Events']}
            >
              <span className={styles.tipsPopupSectionTitle}>Events</span>
              <span>{expandedTipSections['Events'] ? '▼' : '▶'}</span>
            </div>
            {expandedTipSections['Events'] && (
              <div className={styles.tipsPopupSectionContent}>
                <ul>
                  <li><strong>Events</strong> show real-time execution details - JSON-formatted log streamed via SSE or WebSocket</li>
                  <li><strong>Event limit</strong>: UI displays up to 1000 events; the stream auto-terminates past the server limit to prevent memory issues</li>
                  <li><strong>orchestration_plan</strong>: Sent first - shows the full execution graph with skills and recipe boundaries</li>
                  <li><strong>recipe_start</strong> / <strong>recipe_end</strong>: Mark the beginning and end of a recipe block (hierarchical mode) with duration metrics</li>
                  <li><strong>recipe_skipped</strong>: Emitted when a recipe's condition evaluates false (conditional recipes)</li>
                  <li><strong>skill_start</strong>: A skill has begun execution - includes skill name and metadata</li>
                  <li><strong>skill_complete</strong>: A skill finished successfully - includes results and output data for visualizers</li>
                  <li><strong>parallel_start</strong> / <strong>parallel_complete</strong>: Marks parallel skill group execution boundaries</li>
                  <li><strong>metrics</strong>: Aggregated performance data (total time, cache hits/misses, per-skill timing) sent at completion</li>
                  <li><strong>error</strong> / <strong>skill_failed</strong>: Something went wrong - includes error message, request ID, and context</li>
                  <li><strong>heartbeat</strong>: Keeps SSE/WebSocket connections alive during long runs - filtered from the UI log to reduce noise</li>
                  <li><strong>complete</strong>: Final event indicating run status (completed / failed) with any accumulated errors</li>
                  <li><strong>Debugging</strong>: Use the event filter buttons (All, Recipes, Skills, Errors) to focus on specific event types</li>
                </ul>
              </div>
            )}
          </div>

          {/* Graph Section */}
          <div className={styles.tipsPopupSection}>
            <div
              className={styles.tipsPopupSectionHeader}
              onClick={() => toggleTipSection('Graph')}
              onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleTipSection('Graph') } }}
              title="Click to expand/collapse Dependency Graph tips"
              data-section="Graph"
              tabIndex={0}
              role="button"
              aria-expanded={expandedTipSections['Graph']}
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
        <div className={styles.modalOverlay} onClick={() => setLibraryPopupOpen(false)} role="presentation">
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="library-title">
            <div className={styles.modalHeader}>
              <strong id="library-title">📚 Library</strong>
              <button className={styles.modalCloseButton} onClick={() => setLibraryPopupOpen(false)} aria-label="Close library">✕</button>
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
        <div className={styles.modalOverlay} onClick={() => setRecipesPopupOpen(false)} role="presentation">
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="recipes-title">
            <div className={styles.modalHeader}>
              <strong id="recipes-title">📚 Recipes Library</strong>
              <div className={styles.modalHeaderButtons}>
                <button
                  className={styles.primaryButton}
                  onClick={() => {
                    setEditingRecipe({ id: '', label: '', skills: [], hint: '' })
                    setEditRecipeLabel('')
                    setEditRecipeSkills('')
                    setBuilderSkills([])
                    setEditRecipeHint('')
                  }}
                  title="Create new recipe"
                >
                  + New Recipe
                </button>
                <button className={styles.modalCloseButton} onClick={() => setRecipesPopupOpen(false)} aria-label="Close recipes">✕</button>
              </div>
            </div>
            <div className={styles.modalBody}>
              {editingRecipe ? (
                <div className={styles.createFolderRow}>
                  <input
                    type="text"
                    className={styles.createFolderInput}
                    placeholder="Recipe label"
                    value={editRecipeLabel}
                    onChange={(e) => setEditRecipeLabel(e.target.value)}
                  />
                  <div className={styles.builderToggle}>
                    <button
                      className={`${styles.builderToggleButton} ${builderMode ? styles.builderToggleActive : ''}`}
                      onClick={() => setBuilderMode(true)}
                      type="button"
                    >
                      🧱 Builder
                    </button>
                    <button
                      className={`${styles.builderToggleButton} ${!builderMode ? styles.builderToggleActive : ''}`}
                      onClick={() => setBuilderMode(false)}
                      type="button"
                    >
                      📝 Text
                    </button>
                  </div>
                  {builderMode ? (
                    <div className={styles.recipeBuilder}>
                      <div className={styles.builderPalette}>
                        <div className={styles.builderLabel}>Available Skills</div>
                        <div className={styles.builderPaletteSkills}>
                          {(backendSkills.length > 0 ? backendSkills : AVAILABLE_SKILLS.map(s => s.id)).map((skill) => (
                            <div
                              key={skill}
                              className={styles.builderPaletteChip}
                              draggable
                              onDragStart={(e) => {
                                e.dataTransfer.setData('text/uar-builder-skill', skill)
                                e.dataTransfer.effectAllowed = 'copy'
                              }}
                              onClick={() => {
                                if (!builderSkills.includes(skill)) {
                                  setBuilderSkills((prev) => [...prev, skill])
                                  setEditRecipeSkills((prev) => prev ? `${prev}, ${skill}` : skill)
                                }
                              }}
                              title={`Drag or click to add ${skill}`}
                            >
                              + {skill}
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className={styles.builderCanvas}>
                        <div className={styles.builderLabel}>Recipe Skills</div>
                        <div
                          className={styles.builderDropZone}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault()
                            const skill = e.dataTransfer.getData('text/uar-builder-skill')
                            if (skill && !builderSkills.includes(skill)) {
                              setBuilderSkills((prev) => [...prev, skill])
                              setEditRecipeSkills((prev) => prev ? `${prev}, ${skill}` : skill)
                            }
                          }}
                        >
                          {builderSkills.length === 0 ? (
                            <div className={styles.builderEmpty}>Drag skills here or click skills to add them</div>
                          ) : (
                            builderSkills.map((skill, idx) => (
                              <div
                                key={`${skill}-${idx}`}
                                className={styles.builderRecipeChip}
                                draggable
                                onDragStart={(e) => {
                                  e.dataTransfer.setData('text/uar-builder-reorder', String(idx))
                                  e.dataTransfer.effectAllowed = 'move'
                                  setBuilderDragIndex(idx)
                                }}
                                onDragOver={(e) => e.preventDefault()}
                                onDrop={(e) => {
                                  e.preventDefault()
                                  const fromIdx = parseInt(e.dataTransfer.getData('text/uar-builder-reorder'), 10)
                                  const toIdx = idx
                                  if (!Number.isNaN(fromIdx) && fromIdx !== toIdx) {
                                    setBuilderSkills((prev) => {
                                      const next = [...prev]
                                      const [moved] = next.splice(fromIdx, 1)
                                      next.splice(toIdx, 0, moved)
                                      setEditRecipeSkills(next.join(', '))
                                      return next
                                    })
                                  }
                                  setBuilderDragIndex(null)
                                }}
                                onDragEnd={() => setBuilderDragIndex(null)}
                              >
                                <span className={styles.builderRecipeChipIndex}>{idx + 1}</span>
                                <span className={styles.builderRecipeChipName}>{skill}</span>
                                <button
                                  className={styles.builderRecipeChipRemove}
                                  onClick={() => {
                                    setBuilderSkills((prev) => {
                                      const next = prev.filter((_, i) => i !== idx)
                                      setEditRecipeSkills(next.join(', '))
                                      return next
                                    })
                                  }}
                                  title="Remove skill"
                                  aria-label={`Remove ${skill}`}
                                >
                                  ✕
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <input
                      type="text"
                      className={styles.createFolderInput}
                      placeholder="Skills (comma-separated)"
                      value={editRecipeSkills}
                      onChange={(e) => {
                        setEditRecipeSkills(e.target.value)
                        setBuilderSkills(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
                      }}
                    />
                  )}
                  <input
                    type="text"
                    className={styles.createFolderInput}
                    placeholder="Hint"
                    value={editRecipeHint}
                    onChange={(e) => setEditRecipeHint(e.target.value)}
                  />
                  <button
                    className={styles.createFolderButton}
                    onClick={async () => {
                      const skills = builderMode ? [...builderSkills] : editRecipeSkills.split(',').map(s => s.trim()).filter(s => s)

                      // Validate recipe skills against backend registry
                      const validSkillSet = new Set(
                        backendSkills.length > 0
                          ? backendSkills
                          : AVAILABLE_SKILLS.map(s => s.id)
                      )
                      const invalidSkills = skills.filter(s => !validSkillSet.has(s))
                      if (invalidSkills.length > 0) {
                        setError({
                          message: `Invalid skills in recipe: ${invalidSkills.join(', ')}`,
                          timestamp: Date.now(),
                        })
                        return
                      }

                      const newRecipe: Recipe = {
                        id: editingRecipe.id || `custom_${Date.now()}`,
                        label: editRecipeLabel || editingRecipe.label,
                        skills,
                        hint: editRecipeHint || editingRecipe.hint
                      }

                      // Try to persist to backend (user recipes only)
                      const isNew = !editingRecipe.id
                      const url = isNew
                        ? '/api/uar/recipes'
                        : `/api/uar/recipes/${editingRecipe.id}`
                      const method = isNew ? 'POST' : 'PUT'
                      try {
                        const res = await fetch(url, {
                          method,
                          headers: authHeaders({ 'Content-Type': 'application/json' }),
                          body: JSON.stringify(newRecipe),
                        })
                        if (!res.ok && res.status !== 403 && res.status !== 409) {
                          console.warn('Failed to save recipe to backend:', res.status)
                        }
                      } catch (e) {
                        console.warn('Recipe backend sync failed:', e)
                      }

                      setRecipes((prev) => {
                        let newRecipes
                        if (editingRecipe.id) {
                          // Update existing recipe
                          newRecipes = prev.map(r => r.id === editingRecipe.id ? newRecipe : r)
                        } else {
                          // Add new recipe
                          newRecipes = [...prev, newRecipe]
                        }
                        try {
                          getLocalStorage()?.setItem(RECIPES_KEY, JSON.stringify(newRecipes))
                        } catch {
                          /* ignore quota errors */
                        }
                        setRecipeHistory((history) => {
                          const newHistory = [...history.slice(0, recipeHistoryIndexRef.current + 1), newRecipes]
                          setRecipeHistoryIndex((idx) => idx + 1)
                          return newHistory
                        })
                        return newRecipes
                      })
                      setEditingRecipe(null)
                      setEditRecipeLabel('')
                      setEditRecipeSkills('')
                      setBuilderSkills([])
                      setEditRecipeHint('')
                    }}
                  >
                    Save
                  </button>
                  <button
                    className={styles.footerButton}
                    onClick={() => {
                      setEditingRecipe(null)
                      setEditRecipeLabel('')
                      setEditRecipeSkills('')
                      setBuilderSkills([])
                      setEditRecipeHint('')
                    }}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className={styles.libraryPopupList}>
                  {RECIPES.map((r) => (
                    <div
                      key={r.id}
                      className={styles.libraryPopupItem}
                    >
                      <div onClick={() => {
                        // Toggle recipe in the recipes array (only if not in execution order)
                        const isInOrder = unifiedOrder.some(i => i.type === 'recipe' && i.content === r.id)
                        if (isInOrder) {
                          // Don't allow unselecting if recipe is in execution order
                          return
                        }
                        setRecipes((prev) => {
                          if (prev.some(recipe => recipe.id === r.id)) {
                            // Remove if already present
                            const newRecipes = prev.filter(recipe => recipe.id !== r.id)
                            // Update history
                            setRecipeHistory((history) => {
                              const newHistory = [...history.slice(0, recipeHistoryIndexRef.current + 1), newRecipes]
                              setRecipeHistoryIndex((idx) => idx + 1)
                              return newHistory
                            })
                            return newRecipes
                          } else {
                            // Add if not present
                            const newRecipes = [...prev, r]
                            // Update history
                            setRecipeHistory((history) => {
                              const newHistory = [...history.slice(0, recipeHistoryIndexRef.current + 1), newRecipes]
                              setRecipeHistoryIndex((idx) => idx + 1)
                              return newHistory
                            })
                            return newRecipes
                          }
                        })
                      }} onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); (ev.currentTarget as HTMLDivElement).click() } }} tabIndex={0} role="button" aria-label={`${recipes.some(recipe => recipe.id === r.id) ? 'Deselect' : 'Select'} recipe ${r.label}`}>
                        <span className={styles.libraryItemName}>
                          {recipes.some(recipe => recipe.id === r.id) ? '✓ ' : ''}{r.label}
                        </span>
                        <span className={styles.libraryItemSize}>
                          {r.skills.join(', ')}
                        </span>
                      </div>
                      <button
                        className={styles.deleteButton}
                        onClick={(e) => {
                          e.stopPropagation()
                          setEditingRecipe(r)
                          setEditRecipeLabel(r.label)
                          const skillsArr = r.skills.map((s) => (typeof s === 'string' ? s : '')).filter(Boolean)
                          setEditRecipeSkills(skillsArr.join(', '))
                          setBuilderSkills(skillsArr)
                          setEditRecipeHint(r.hint || '')
                        }}
                        title="Edit recipe"
                        aria-label={`Edit recipe ${r.label}`}
                      >
                        ✏️
                      </button>
                      <button
                        className={styles.deleteButton}
                        onClick={async (e) => {
                          e.stopPropagation()
                          if (!confirm(`Delete recipe "${r.label}"?`)) return
                          try {
                            const res = await fetch(`/api/uar/recipes/${r.id}`, {
                              method: 'DELETE',
                              headers: authHeaders(),
                            })
                            if (!res.ok) {
                              const err = await res.json().catch(() => ({}))
                              setError({ message: err.message || `Failed to delete recipe: ${res.status}`, timestamp: Date.now() })
                              return
                            }
                            setRecipes((prev) => {
                              const next = prev.filter((rec) => rec.id !== r.id)
                              setRecipeHistory((history) => {
                                const newHistory = [...history.slice(0, recipeHistoryIndexRef.current + 1), next]
                                setRecipeHistoryIndex((idx) => idx + 1)
                                return newHistory
                              })
                              return next
                            })
                            setUnifiedOrder((prev) => prev.filter((item) => item.type !== 'recipe' || item.content !== r.id))
                          } catch (err) {
                            setError({ message: err instanceof Error ? err.message : 'Delete failed', timestamp: Date.now() })
                          }
                        }}
                        title="Delete recipe"
                        aria-label={`Delete recipe ${r.label}`}
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.footerButton} onClick={() => setRecipesPopupOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Runs History Panel */}
      {showRunsPanel && (
        <div className={styles.modalOverlay} onClick={() => setShowRunsPanel(false)} role="presentation">
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="runs-title">
            <div className={styles.modalHeader}>
              <strong id="runs-title">📜 Runs History</strong>
              <button className={styles.modalCloseButton} onClick={() => setShowRunsPanel(false)} aria-label="Close runs history">✕</button>
            </div>
            <div className={styles.modalBody}>
              {runsHistory.length === 0 ? (
                <div className={styles.runsEmptyMessage}>
                  No runs found. Execute a run to build history.
                </div>
              ) : (
                <div className={styles.libraryPopupList}>
                  {runsHistory.map((run) => (
                    <div key={run.run_id || run.id} className={styles.libraryPopupItem}>
                      <div className={styles.runsItemContent}>
                        <span className={styles.libraryItemName}>
                          {run.goal_id || 'Run'} — {run.status || 'unknown'}
                        </span>
                        <span className={styles.libraryItemSize}>
                          {run.skills?.length || 0} skills · {run.events?.length || 0} events
                        </span>
                      </div>
                      <button
                        className={styles.createFolderButton}
                        onClick={() => {
                          if (run.events && Array.isArray(run.events)) {
                            setEvents(run.events)
                            eventCountRef.current = run.events.length
                          }
                          setShowRunsPanel(false)
                        }}
                        title="Replay events"
                      >
                        Replay
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.footerButton} onClick={() => setShowRunsPanel(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
    </div>
  )
}

export default UARPanel
