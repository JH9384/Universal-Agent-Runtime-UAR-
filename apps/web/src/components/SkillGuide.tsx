import { useState } from 'react'
import styles from './SkillGuide.module.css'

type Skill = {
  id: string
  label: string
  desc: string
  useCase: string
  example: string
  prerequisites?: string[]
  output: string
  category: 'Core' | 'AI' | 'GraphRAG' | 'Storage' | 'Analysis' | 'Ecosystem'
}

const SKILLS: Skill[] = [
  {
    id: 'doc_ingest',
    label: 'doc_ingest',
    desc: 'Read files from input_path (.md .txt .py .ts .json .pdf .docx .xlsx .ipynb)',
    useCase: 'Load documents for analysis or processing',
    example: 'Goal: "Analyze the codebase" → Skills: [doc_ingest, dependency_map]',
    output: 'List of documents with text content, file paths, and metadata',
    category: 'Core'
  },
  {
    id: 'dependency_map',
    label: 'dependency_map',
    desc: 'Build a dependency graph between artifacts',
    useCase: 'Understand code structure and relationships',
    example: 'Goal: "Map project dependencies" → Skills: [doc_ingest, dependency_map]',
    prerequisites: ['doc_ingest'],
    output: 'Graph nodes (files) and edges (import relationships)',
    category: 'Core'
  },
  {
    id: 'section_sum',
    label: 'section_sum',
    desc: 'Summarize document sections',
    useCase: 'Quick overview of document content',
    example: 'Goal: "Summarize README" → Skills: [doc_ingest, section_sum]',
    prerequisites: ['doc_ingest'],
    output: 'Summary text of the processed goal',
    category: 'Core'
  },
  {
    id: 'sum_review',
    label: 'sum_review',
    desc: 'Final review of pipeline outputs',
    useCase: 'Aggregate and review all pipeline results',
    example: 'Goal: "Review analysis" → Skills: [doc_ingest, dependency_map, sum_review]',
    output: 'Skills executed, event count, and observations',
    category: 'Core'
  },
  {
    id: 'ollama_generate',
    label: 'ollama_generate',
    desc: 'Send goal + ingested docs to local Ollama model',
    useCase: 'AI-powered analysis and generation',
    example: 'Goal: "Explain this code" → Skills: [doc_ingest, ollama_generate]',
    prerequisites: ['doc_ingest', 'Ollama running locally'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'graphrag_init',
    label: 'graphrag_init',
    desc: 'Initialize GraphRAG workspace for knowledge graph',
    useCase: 'Set up GraphRAG for a codebase or document set',
    example: 'Goal: "Initialize GraphRAG" → Skills: [graphrag_init]',
    output: 'Workspace initialization status and configuration',
    category: 'GraphRAG'
  },
  {
    id: 'graphrag_index',
    label: 'graphrag_index',
    desc: 'Build GraphRAG knowledge graph over input_path (slow; one-time)',
    useCase: 'Create searchable knowledge graph from documents',
    example: 'Goal: "Index all docs" → Skills: [graphrag_index]',
    prerequisites: ['graphrag_init'],
    output: 'Indexing statistics and graph metadata',
    category: 'GraphRAG'
  },
  {
    id: 'graphrag_query',
    label: 'graphrag_query',
    desc: 'Query the GraphRAG index (local or global method)',
    useCase: 'Ask questions about indexed knowledge',
    example: 'Goal: "What are the main themes?" → Skills: [graphrag_query]',
    prerequisites: ['graphrag_index'],
    output: 'Query results with sources and relevance scores',
    category: 'GraphRAG'
  },
  {
    id: 'autonomi_upload',
    label: 'autonomi_upload',
    desc: 'Upload file/dir to Autonomi decentralized storage',
    useCase: 'Store data permanently on decentralized network',
    example: 'Goal: "Backup to Autonomi" → Skills: [autonomi_upload]',
    prerequisites: ['autonomi package installed', 'wallet configured'],
    output: 'Autonomi address and upload status',
    category: 'Storage'
  },
  {
    id: 'autonomi_download',
    label: 'autonomi_download',
    desc: 'Download a file from Autonomi by address',
    useCase: 'Retrieve data from decentralized storage',
    example: 'Goal: "Download from Autonomi" → Skills: [autonomi_download]',
    prerequisites: ['autonomi package installed', 'Autonomi address'],
    output: 'Download status and file location',
    category: 'Storage'
  },
  {
    id: 'autonomi_status',
    label: 'autonomi_status',
    desc: 'Check Autonomi client and wallet status',
    useCase: 'Verify Autonomi connectivity before upload/download',
    example: 'Goal: "Check Autonomi" → Skills: [autonomi_status]',
    prerequisites: ['autonomi package installed'],
    output: 'Connection status, wallet info, package version',
    category: 'Storage'
  },
  {
    id: 'alm_analyze',
    label: 'alm_analyze',
    desc: 'Analyze formal grammar specifications (BNF, EBNF) with ALM',
    useCase: 'Verify grammar correctness and provability',
    example: 'Goal: "Analyze grammar" → Skills: [alm_analyze]',
    prerequisites: ['ALM service running'],
    output: 'Analysis results with status and details',
    category: 'Analysis'
  },
  {
    id: 'alm_generate',
    label: 'alm_generate',
    desc: 'Generate token sequences from a prefix using ALM',
    useCase: 'Generate valid sequences from formal grammars',
    example: 'Goal: "Generate sequence" → Skills: [alm_generate]',
    prerequisites: ['ALM service running'],
    output: 'Generated token sequence',
    category: 'Analysis'
  },
  {
    id: 'alm_verify',
    label: 'alm_verify',
    desc: 'Validate text against ALM grammar',
    useCase: 'Check if text conforms to formal grammar',
    example: 'Goal: "Verify syntax" → Skills: [alm_verify]',
    prerequisites: ['ALM service running'],
    output: 'Validation status with proof ID if valid',
    category: 'Analysis'
  },
  {
    id: 'uor_addr_canonicalize',
    label: 'uor_addr_canonicalize',
    desc: 'Canonicalize data per UOR-ADDR-1 and compute SHA-256 digest',
    useCase: 'Create content-addressed identity for any data',
    example: 'Goal: "Canonicalize payload" → Skills: [uor_addr_canonicalize]',
    output: 'Digest envelope with canonical bytes, size, and mediaType',
    category: 'Ecosystem'
  },
  {
    id: 'uor_addr_resolve',
    label: 'uor_addr_resolve',
    desc: 'Resolve a UOR digest from the integrator object cache',
    useCase: 'Retrieve previously canonicalized data by digest',
    example: 'Goal: "Resolve digest" → Skills: [uor_addr_resolve]',
    output: 'UOR object data, provenance, and metadata',
    category: 'Ecosystem'
  },
  {
    id: 'hologram_query',
    label: 'hologram_query',
    desc: 'Submit geometric inference to gethologram.ai',
    useCase: 'Run geometric virtual compute inference',
    example: 'Goal: "Infer embedding" → Skills: [hologram_query]',
    prerequisites: ['HOLOGRAM_API_KEY configured'],
    output: 'Inference results with model outputs',
    category: 'Ecosystem'
  },
  {
    id: 'hologram_status',
    label: 'hologram_status',
    desc: 'Check gethologram.ai service health',
    useCase: 'Verify Hologram API availability before queries',
    example: 'Goal: "Check Hologram" → Skills: [hologram_status]',
    output: 'Service status, reachability, and status code',
    category: 'Ecosystem'
  },
  {
    id: 'moltbook_list',
    label: 'moltbook_list',
    desc: 'List recent topics from moltbook.com/m/uor forum',
    useCase: 'Browse community discussions',
    example: 'Goal: "Browse forum" → Skills: [moltbook_list]',
    output: 'List of forum topics with titles and metadata',
    category: 'Ecosystem'
  },
  {
    id: 'moltbook_search',
    label: 'moltbook_search',
    desc: 'Search moltbook.com/m/uor forum posts',
    useCase: 'Find specific discussions in the community',
    example: 'Goal: "Search forum" → Skills: [moltbook_search]',
    output: 'Search results matching query',
    category: 'Ecosystem'
  },
  {
    id: 'moltbook_post',
    label: 'moltbook_post',
    desc: 'Post a new topic to the moltbook forum',
    useCase: 'Share findings with the UOR community',
    example: 'Goal: "Post update" → Skills: [moltbook_post]',
    prerequisites: ['MOLTBOOK_API_KEY configured'],
    output: 'Post status and topic URL',
    category: 'Ecosystem'
  },
  {
    id: 'prism_btc_anchor',
    label: 'prism_btc_anchor',
    desc: 'Anchor a UOR digest on Bitcoin (placeholder)',
    useCase: 'Create blockchain proof-of-existence for data',
    example: 'Goal: "Anchor digest" → Skills: [prism_btc_anchor]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'prism_btc_verify',
    label: 'prism_btc_verify',
    desc: 'Verify an on-chain Bitcoin anchor (placeholder)',
    useCase: 'Confirm blockchain proof-of-existence',
    example: 'Goal: "Verify anchor" → Skills: [prism_btc_verify]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'severance_infer',
    label: 'severance_infer',
    desc: 'Run inference via Severance AI (placeholder)',
    useCase: 'Modular AI inference with separation of concerns',
    example: 'Goal: "Run inference" → Skills: [severance_infer]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'severance_verify',
    label: 'severance_verify',
    desc: 'Verify Severance AI output (placeholder)',
    useCase: 'Formal verification of AI outputs',
    example: 'Goal: "Verify output" → Skills: [severance_verify]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'anunix_health',
    label: 'anunix_health',
    desc: 'Check Anunix host health (placeholder)',
    useCase: 'Monitor self-healing infrastructure',
    example: 'Goal: "Check host" → Skills: [anunix_health]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'anunix_run',
    label: 'anunix_run',
    desc: 'Run command on Anunix host (placeholder)',
    useCase: 'Remote execution on managed hosts',
    example: 'Goal: "Run remote command" → Skills: [anunix_run]',
    output: 'Placeholder status (pending public API)',
    category: 'Ecosystem'
  },
  {
    id: 'uor_ecosystem_status',
    label: 'uor_ecosystem_status',
    desc: 'Check status of all UOR ecosystem integrations',
    useCase: 'Health monitoring of all ecosystem connections',
    example: 'Goal: "Status check" → Skills: [uor_ecosystem_status]',
    output: 'Status map for all 6 ecosystem integrations',
    category: 'Ecosystem'
  },
  {
    id: 'molecular_visualization',
    label: 'molecular_visualization',
    desc: 'Generate 3D molecular structure visualizations',
    useCase: 'Visualize molecular structures with interactive 3D rendering',
    example: 'Goal: "Show molecule" → Skills: [molecular_visualization]',
    output: '3D molecular data with atoms, bonds, and element colors',
    category: 'Analysis'
  },
  {
    id: 'quantum_circuit_visualization',
    label: 'quantum_circuit_visualization',
    desc: 'Generate 3D quantum circuit layouts',
    useCase: 'Visualize quantum circuits with qubit tracks, gates, and entanglement connections',
    example: 'Goal: "Show quantum circuit" → Skills: [quantum_circuit_visualization]',
    output: '3D quantum circuit data with gates, qubit tracks, and entanglements',
    category: 'Analysis'
  },
  {
    id: 'trefoil_simulation',
    label: 'trefoil_simulation',
    desc: 'Simulate and visualize 3D trefoil knot dynamics',
    useCase: 'Interactive 3D trefoil knot simulation with parameter controls',
    example: 'Goal: "Simulate trefoil" → Skills: [trefoil_simulation]',
    output: '3D trefoil knot data with keyframes, expansion, and rotation controls',
    category: 'Analysis'
  },
  {
    id: 'data_viz_3d',
    label: 'data_viz_3d',
    desc: 'Generate 3D mesh visualizations',
    useCase: 'Create interactive 3D mesh renders from geometric data',
    example: 'Goal: "Visualize mesh" → Skills: [data_viz_3d]',
    output: '3D mesh data with vertices, normals, and face indices',
    category: 'Analysis'
  },
  {
    id: 'verilog_parse',
    label: 'verilog_parse',
    desc: 'Parse Verilog HDL source code for module analysis',
    useCase: 'Extract modules, ports, signals, and instances from Verilog',
    example: 'Goal: "Parse Verilog" → Skills: [verilog_parse]',
    output: 'Module hierarchy, port definitions, signal declarations, and instance connections',
    category: 'Analysis'
  },
  {
    id: 'fpga_verify',
    label: 'fpga_verify',
    desc: 'Verify Verilog modules with generated test vectors',
    useCase: 'Generate pseudo-random test vectors and verify combinational logic',
    example: 'Goal: "Verify FPGA module" → Skills: [verilog_parse, fpga_verify]',
    prerequisites: ['verilog_parse'],
    output: 'Test vector results, waveform metadata, pass/fail assertions',
    category: 'Analysis'
  },
  {
    id: 'riscv_sim',
    label: 'riscv_sim',
    desc: 'Simulate RISC-V assembly programs',
    useCase: 'Emulate RISC-V instructions with symbol support and flexible execution',
    example: 'Goal: "Simulate RISC-V" → Skills: [riscv_sim]',
    output: 'Execution trace, register state, and memory contents',
    category: 'Analysis'
  },
  {
    id: 'physics_compute',
    label: 'physics_compute',
    desc: 'Physics and astronomy calculations',
    useCase: 'Unit conversions, coordinate transforms, cosmology computations',
    example: 'Goal: "Convert units" → Skills: [physics_compute]',
    output: 'Computed physics values with units and precision',
    category: 'Analysis'
  },
  {
    id: 'math_compute',
    label: 'math_compute',
    desc: 'Symbolic math with SymPy',
    useCase: 'Solve equations, differentiate, integrate, simplify expressions',
    example: 'Goal: "Solve equation" → Skills: [math_compute]',
    output: 'Symbolic math results and numerical evaluations',
    category: 'Analysis'
  },
  {
    id: 'cipher_ops',
    label: 'cipher_ops',
    desc: 'Cryptographic operations',
    useCase: 'Encrypt/decrypt data, hash functions, digital signatures',
    example: 'Goal: "Encrypt data" → Skills: [cipher_ops]',
    output: 'Encrypted/decrypted data, hashes, or signatures',
    category: 'Analysis'
  },
  {
    id: 'openai_skills',
    label: 'openai_skills',
    desc: 'OpenAI GPT models for text generation and analysis',
    useCase: 'Chat, completion, embeddings with GPT-4 and GPT-3.5',
    example: 'Goal: "Analyze with GPT" → Skills: [doc_ingest, openai_skills]',
    prerequisites: ['doc_ingest', 'OPENAI_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'anthropic_skills',
    label: 'anthropic_skills',
    desc: 'Anthropic Claude models for high-quality reasoning',
    useCase: 'Claude 3 Opus, Sonnet, Haiku for complex reasoning tasks',
    example: 'Goal: "Reason about code" → Skills: [doc_ingest, anthropic_skills]',
    prerequisites: ['doc_ingest', 'ANTHROPIC_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'gemini_skills',
    label: 'gemini_skills',
    desc: 'Google Gemini models for multimodal capabilities',
    useCase: 'Gemini Pro for text, image, and multimodal tasks',
    example: 'Goal: "Analyze with Gemini" → Skills: [doc_ingest, gemini_skills]',
    prerequisites: ['doc_ingest', 'GEMINI_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'mistral_skills',
    label: 'mistral_skills',
    desc: 'Mistral models for efficient inference',
    useCase: 'Mistral 7B, Mixtral for fast local and cloud inference',
    example: 'Goal: "Generate with Mistral" → Skills: [doc_ingest, mistral_skills]',
    prerequisites: ['doc_ingest', 'MISTRAL_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'groq_skills',
    label: 'groq_skills',
    desc: 'Groq ultra-fast inference with LPU acceleration',
    useCase: 'Real-time responses with LPU-accelerated inference',
    example: 'Goal: "Fast inference" → Skills: [doc_ingest, groq_skills]',
    prerequisites: ['doc_ingest', 'GROQ_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'huggingface_skills',
    label: 'huggingface_skills',
    desc: 'Hugging Face models via Inference API',
    useCase: 'Access thousands of models via Hugging Face Inference API',
    example: 'Goal: "Run HF model" → Skills: [doc_ingest, huggingface_skills]',
    prerequisites: ['doc_ingest', 'HF_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'together_skills',
    label: 'together_skills',
    desc: 'Together.ai optimized open-source models',
    useCase: 'Fast inference with optimized open-source models',
    example: 'Goal: "Run Together model" → Skills: [doc_ingest, together_skills]',
    prerequisites: ['doc_ingest', 'TOGETHER_API_KEY'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  },
  {
    id: 'lm_studio_skills',
    label: 'lm_studio_skills',
    desc: 'Local models via LM Studio',
    useCase: 'Run local LLMs with LM Studio GUI interface',
    example: 'Goal: "Local inference" → Skills: [doc_ingest, lm_studio_skills]',
    prerequisites: ['doc_ingest', 'LM Studio running locally'],
    output: 'AI-generated response with model info and context stats',
    category: 'AI'
  }
]

const CATEGORIES = ['Core', 'AI', 'GraphRAG', 'Storage', 'Analysis', 'Ecosystem'] as const

export function SkillGuide() {
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [filterCategory, setFilterCategory] = useState<string>('All')

  const filteredSkills = filterCategory === 'All'
    ? SKILLS
    : SKILLS.filter(s => s.category === filterCategory)

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>📘 Skill Guide</h3>

      {/* Category Filter */}
      <div className={styles.filterContainer}>
        <span className={styles.filterLabel}>Filter:</span>
        <button
          onClick={() => setFilterCategory('All')}
          className={`${styles.filterButton} ${filterCategory === 'All' ? styles.active : ''}`}
        >
          All
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            className={`${styles.filterButton} ${filterCategory === cat ? styles.active : ''}`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Skill List */}
      <div className={styles.skillList}>
        {filteredSkills.map(skill => (
          <div
            key={skill.id}
            onClick={() => setSelectedSkill(skill)}
            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); setSelectedSkill(skill) } }}
            tabIndex={0}
            role="button"
            aria-label={`View details for ${skill.label}`}
            className={styles.skillCard}
          >
            <div className={styles.skillHeader}>
              <strong className={styles.skillLabel}>{skill.label}</strong>
              <span className={styles.skillCategory}>
                {skill.category}
              </span>
            </div>
            <div className={styles.skillDescription}>
              {skill.desc}
            </div>
          </div>
        ))}
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <div
          onClick={() => setSelectedSkill(null)}
          className={styles.modalOverlay}
          role="presentation"
        >
          <div
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
            className={styles.modalContent}
            role="dialog"
            aria-modal="true"
            aria-labelledby="skill-detail-title"
          >
            <div className={styles.modalHeader}>
              <h4 id="skill-detail-title" className={styles.modalTitle}>{selectedSkill.label}</h4>
              <button
                onClick={() => setSelectedSkill(null)}
                className={styles.closeButton}
                aria-label="Close skill details"
              >
                ✕
              </button>
            </div>

            <div className={styles.modalSection}>
              <span className={styles.modalCategory}>
                {selectedSkill.category}
              </span>
            </div>

            <div className={styles.modalSection}>
              <strong className={styles.modalLabel}>Description:</strong>
              <div className={styles.modalText}>{selectedSkill.desc}</div>
            </div>

            <div className={styles.modalSection}>
              <strong className={styles.modalLabel}>When to use:</strong>
              <div className={styles.modalText}>{selectedSkill.useCase}</div>
            </div>

            <div className={styles.modalSection}>
              <strong className={styles.modalLabel}>Example:</strong>
              <div className={styles.exampleBox}>
                {selectedSkill.example}
              </div>
            </div>

            {selectedSkill.prerequisites && (
              <div className={styles.modalSection}>
                <strong className={styles.modalLabel}>Prerequisites:</strong>
                <div>
                  {selectedSkill.prerequisites.map(prereq => (
                    <span
                      key={prereq}
                      className={styles.prerequisite}
                    >
                      {prereq}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <strong className={styles.modalLabel}>Output:</strong>
              <div className={styles.modalText}>{selectedSkill.output}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
