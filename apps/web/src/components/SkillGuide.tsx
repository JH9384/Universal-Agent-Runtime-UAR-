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
    id: 'doc_ingest_enhanced',
    label: 'doc_ingest_enhanced',
    desc: 'Advanced document ingestion with Unstructured & Docling',
    useCase: 'Parse PDFs, DOCX, images, tables with layout preservation',
    example: 'Goal: "Extract tables from PDF" → Skills: [doc_ingest_enhanced]',
    prerequisites: ['unstructured', 'docling'],
    output: 'Structured document content with tables and images',
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
    id: 'openai_chat',
    label: 'openai_chat',
    desc: 'Chat with OpenAI GPT models',
    useCase: 'Conversational AI with GPT-4 and GPT-3.5',
    example: 'Goal: "Chat about this topic" → Skills: [doc_ingest, openai_chat]',
    prerequisites: ['doc_ingest', 'OPENAI_API_KEY'],
    output: 'AI chat response with model info',
    category: 'AI'
  },
  {
    id: 'openai_completion',
    label: 'openai_completion',
    desc: 'Text completion with OpenAI GPT models',
    useCase: 'Generate text, code, summaries with GPT',
    example: 'Goal: "Complete this sentence" → Skills: [openai_completion]',
    prerequisites: ['OPENAI_API_KEY'],
    output: 'Generated text completion',
    category: 'AI'
  },
  {
    id: 'openai_embedding',
    label: 'openai_embedding',
    desc: 'Generate embeddings with OpenAI models',
    useCase: 'Text embeddings for similarity search and clustering',
    example: 'Goal: "Embed these documents" → Skills: [doc_ingest, openai_embedding]',
    prerequisites: ['doc_ingest', 'OPENAI_API_KEY'],
    output: 'Vector embeddings array',
    category: 'AI'
  },
  {
    id: 'anthropic_chat',
    label: 'anthropic_chat',
    desc: 'Chat with Anthropic Claude models',
    useCase: 'High-quality reasoning with Claude 3 Opus, Sonnet, Haiku',
    example: 'Goal: "Reason about this code" → Skills: [doc_ingest, anthropic_chat]',
    prerequisites: ['doc_ingest', 'ANTHROPIC_API_KEY'],
    output: 'Claude chat response',
    category: 'AI'
  },
  {
    id: 'anthropic_completion',
    label: 'anthropic_completion',
    desc: 'Text completion with Anthropic Claude',
    useCase: 'Generate text with Claude models',
    example: 'Goal: "Write a summary" → Skills: [anthropic_completion]',
    prerequisites: ['ANTHROPIC_API_KEY'],
    output: 'Claude text completion',
    category: 'AI'
  },
  {
    id: 'anthropic_embedding',
    label: 'anthropic_embedding',
    desc: 'Generate embeddings with Claude (not currently supported)',
    useCase: 'Text embeddings with Anthropic models',
    example: 'Goal: "Embed with Claude" → Skills: [doc_ingest, anthropic_embedding]',
    prerequisites: ['doc_ingest', 'ANTHROPIC_API_KEY'],
    output: 'Claude embeddings array',
    category: 'AI'
  },
  {
    id: 'gemini_chat',
    label: 'gemini_chat',
    desc: 'Chat with Google Gemini models',
    useCase: 'Multimodal chat with Gemini Pro',
    example: 'Goal: "Analyze this image" → Skills: [doc_ingest, gemini_chat]',
    prerequisites: ['doc_ingest', 'GEMINI_API_KEY'],
    output: 'Gemini chat response',
    category: 'AI'
  },
  {
    id: 'gemini_completion',
    label: 'gemini_completion',
    desc: 'Text completion with Google Gemini',
    useCase: 'Generate text with Gemini models',
    example: 'Goal: "Generate content" → Skills: [gemini_completion]',
    prerequisites: ['GEMINI_API_KEY'],
    output: 'Gemini text completion',
    category: 'AI'
  },
  {
    id: 'gemini_embedding',
    label: 'gemini_embedding',
    desc: 'Generate embeddings with Google Gemini',
    useCase: 'Text embeddings with Gemini models',
    example: 'Goal: "Embed text" → Skills: [doc_ingest, gemini_embedding]',
    prerequisites: ['doc_ingest', 'GEMINI_API_KEY'],
    output: 'Gemini embeddings array',
    category: 'AI'
  },
  {
    id: 'mistral_chat',
    label: 'mistral_chat',
    desc: 'Chat with Mistral models',
    useCase: 'Fast inference with Mistral 7B, Mixtral',
    example: 'Goal: "Chat with Mistral" → Skills: [doc_ingest, mistral_chat]',
    prerequisites: ['doc_ingest', 'MISTRAL_API_KEY'],
    output: 'Mistral chat response',
    category: 'AI'
  },
  {
    id: 'mistral_completion',
    label: 'mistral_completion',
    desc: 'Text completion with Mistral',
    useCase: 'Generate text with Mistral models',
    example: 'Goal: "Complete text" → Skills: [mistral_completion]',
    prerequisites: ['MISTRAL_API_KEY'],
    output: 'Mistral text completion',
    category: 'AI'
  },
  {
    id: 'mistral_embedding',
    label: 'mistral_embedding',
    desc: 'Generate embeddings with Mistral',
    useCase: 'Text embeddings with Mistral models',
    example: 'Goal: "Embed documents" → Skills: [doc_ingest, mistral_embedding]',
    prerequisites: ['doc_ingest', 'MISTRAL_API_KEY'],
    output: 'Mistral embeddings array',
    category: 'AI'
  },
  {
    id: 'groq_chat',
    label: 'groq_chat',
    desc: 'Ultra-fast chat with Groq LPU acceleration',
    useCase: 'Real-time chat with LPU-accelerated inference',
    example: 'Goal: "Fast chat" → Skills: [doc_ingest, groq_chat]',
    prerequisites: ['doc_ingest', 'GROQ_API_KEY'],
    output: 'Groq chat response',
    category: 'AI'
  },
  {
    id: 'groq_completion',
    label: 'groq_completion',
    desc: 'Ultra-fast completion with Groq',
    useCase: 'Real-time text completion with LPU acceleration',
    example: 'Goal: "Fast completion" → Skills: [groq_completion]',
    prerequisites: ['GROQ_API_KEY'],
    output: 'Groq text completion',
    category: 'AI'
  },
  {
    id: 'groq_embedding',
    label: 'groq_embedding',
    desc: 'Generate embeddings with Groq',
    useCase: 'Fast embeddings with LPU acceleration',
    example: 'Goal: "Fast embeddings" → Skills: [doc_ingest, groq_embedding]',
    prerequisites: ['doc_ingest', 'GROQ_API_KEY'],
    output: 'Groq embeddings array',
    category: 'AI'
  },
  {
    id: 'huggingface_chat',
    label: 'huggingface_chat',
    desc: 'Chat with Hugging Face models',
    useCase: 'Access thousands of models via HF Inference API',
    example: 'Goal: "Chat with HF model" → Skills: [doc_ingest, huggingface_chat]',
    prerequisites: ['doc_ingest', 'HF_API_KEY'],
    output: 'HF chat response',
    category: 'AI'
  },
  {
    id: 'huggingface_completion',
    label: 'huggingface_completion',
    desc: 'Text completion with Hugging Face',
    useCase: 'Generate text with HF models',
    example: 'Goal: "Complete with HF" → Skills: [huggingface_completion]',
    prerequisites: ['HF_API_KEY'],
    output: 'HF text completion',
    category: 'AI'
  },
  {
    id: 'huggingface_embedding',
    label: 'huggingface_embedding',
    desc: 'Generate embeddings with Hugging Face',
    useCase: 'Text embeddings with HF models',
    example: 'Goal: "Embed with HF" → Skills: [doc_ingest, huggingface_embedding]',
    prerequisites: ['doc_ingest', 'HF_API_KEY'],
    output: 'HF embeddings array',
    category: 'AI'
  },
  {
    id: 'together_chat',
    label: 'together_chat',
    desc: 'Chat with Together.ai models',
    useCase: 'Fast inference with optimized open-source models',
    example: 'Goal: "Chat with Together" → Skills: [doc_ingest, together_chat]',
    prerequisites: ['doc_ingest', 'TOGETHER_API_KEY'],
    output: 'Together chat response',
    category: 'AI'
  },
  {
    id: 'together_completion',
    label: 'together_completion',
    desc: 'Text completion with Together.ai',
    useCase: 'Generate text with Together models',
    example: 'Goal: "Complete with Together" → Skills: [together_completion]',
    prerequisites: ['TOGETHER_API_KEY'],
    output: 'Together text completion',
    category: 'AI'
  },
  {
    id: 'together_embedding',
    label: 'together_embedding',
    desc: 'Generate embeddings with Together.ai',
    useCase: 'Text embeddings with Together models',
    example: 'Goal: "Embed with Together" → Skills: [doc_ingest, together_embedding]',
    prerequisites: ['doc_ingest', 'TOGETHER_API_KEY'],
    output: 'Together embeddings array',
    category: 'AI'
  },
  {
    id: 'lm_studio_chat',
    label: 'lm_studio_chat',
    desc: 'Local chat with LM Studio',
    useCase: 'Run local LLMs with LM Studio GUI',
    example: 'Goal: "Local chat" → Skills: [doc_ingest, lm_studio_chat]',
    prerequisites: ['doc_ingest', 'LM Studio running locally'],
    output: 'LM Studio chat response',
    category: 'AI'
  },
  {
    id: 'lm_studio_completion',
    label: 'lm_studio_completion',
    desc: 'Local completion with LM Studio',
    useCase: 'Generate text with local LM Studio models',
    example: 'Goal: "Local completion" → Skills: [lm_studio_completion]',
    prerequisites: ['LM Studio running locally'],
    output: 'LM Studio text completion',
    category: 'AI'
  },
  // STEM / Advanced Analysis
  {
    id: 'scipy_opt',
    label: 'scipy_opt',
    desc: 'SciPy optimization and linear algebra',
    useCase: 'Minimize functions, solve linear systems, eigenvalue problems',
    example: 'Goal: "Optimize this function" → Skills: [scipy_opt]',
    prerequisites: ['scipy'],
    output: 'Optimization results or eigenvalues/eigenvectors',
    category: 'Analysis'
  },
  {
    id: 'diff_eq_solve',
    label: 'diff_eq_solve',
    desc: 'Solve differential equations with SciPy',
    useCase: 'ODE and PDE solving for physics and engineering',
    example: 'Goal: "Solve this ODE" → Skills: [diff_eq_solve]',
    prerequisites: ['scipy'],
    output: 'Solution arrays and metadata',
    category: 'Analysis'
  },
  {
    id: 'quantum_circuit',
    label: 'quantum_circuit',
    desc: 'Quantum circuit design and simulation with Qiskit',
    useCase: 'Build and simulate quantum circuits',
    example: 'Goal: "Design a Bell state circuit" → Skills: [quantum_circuit]',
    prerequisites: ['qiskit'],
    output: 'Circuit metrics and statevector data',
    category: 'Analysis'
  },
  {
    id: 'chem_analysis',
    label: 'chem_analysis',
    desc: 'Chemical analysis with RDKit',
    useCase: 'Molecular fingerprinting, similarity, descriptors',
    example: 'Goal: "Analyze this molecule" → Skills: [chem_analysis]',
    prerequisites: ['rdkit'],
    output: 'Molecular descriptors and similarity scores',
    category: 'Analysis'
  },
  {
    id: 'bio_compute',
    label: 'bio_compute',
    desc: 'Bioinformatics with Biopython',
    useCase: 'Sequence analysis, protein structure, BLAST queries',
    example: 'Goal: "Analyze this DNA sequence" → Skills: [bio_compute]',
    prerequisites: ['biopython'],
    output: 'Sequence stats and alignment results',
    category: 'Analysis'
  },
  {
    id: 'relativity',
    label: 'relativity',
    desc: 'Symbolic relativity with SymPy',
    useCase: 'Metric tensor, Christoffel symbols, geodesic equations',
    example: 'Goal: "Calculate Christoffel symbols" → Skills: [relativity]',
    prerequisites: ['sympy'],
    output: 'Symbolic tensor expressions',
    category: 'Analysis'
  },
  // CV / Image
  {
    id: 'opencv_process',
    label: 'opencv_process',
    desc: 'OpenCV image processing',
    useCase: 'Grayscale, blur, edge detection, contours, resize',
    example: 'Goal: "Detect edges in this image" → Skills: [opencv_process]',
    prerequisites: ['opencv-python'],
    output: 'Processed image path and shape info',
    category: 'Analysis'
  },
  {
    id: 'yolo_detect',
    label: 'yolo_detect',
    desc: 'YOLO object detection',
    useCase: 'Real-time object detection with Ultralytics YOLO',
    example: 'Goal: "Find objects in this image" → Skills: [yolo_detect]',
    prerequisites: ['ultralytics'],
    output: 'Detection results with bounding boxes',
    category: 'Analysis'
  },
  // ML Tools
  {
    id: 'optuna_tune',
    label: 'optuna_tune',
    desc: 'Hyperparameter optimization with Optuna',
    useCase: 'Automated ML hyperparameter tuning',
    example: 'Goal: "Tune these hyperparameters" → Skills: [optuna_tune]',
    prerequisites: ['optuna'],
    output: 'Best params and optimization history',
    category: 'AI'
  },
  {
    id: 'chromadb_store',
    label: 'chromadb_store',
    desc: 'Vector store operations with ChromaDB',
    useCase: 'Add, query, delete vector embeddings',
    example: 'Goal: "Store these embeddings" → Skills: [chromadb_store]',
    prerequisites: ['chromadb'],
    output: 'ChromaDB operation results',
    category: 'AI'
  },
  {
    id: 'lm_studio_embedding',
    label: 'lm_studio_embedding',
    desc: 'Local embeddings with LM Studio',
    useCase: 'Generate embeddings with local LM Studio models',
    example: 'Goal: "Local embeddings" → Skills: [doc_ingest, lm_studio_embedding]',
    prerequisites: ['doc_ingest', 'LM Studio running locally'],
    output: 'LM Studio embeddings array',
    category: 'AI'
  },
  // GraphRAG
  {
    id: 'flexible_graphrag',
    label: 'flexible_graphrag',
    desc: 'Flexible GraphRAG with multiple backends',
    useCase: 'Knowledge graph RAG with Neo4j, Memgraph, RDF',
    example: 'Goal: "Query knowledge graph" → Skills: [doc_ingest, flexible_graphrag]',
    prerequisites: ['doc_ingest'],
    output: 'Graph query results with sources',
    category: 'GraphRAG'
  },
  // Hardware / Embedded
  {
    id: 'myhdl_design',
    label: 'myhdl_design',
    desc: 'Hardware design with MyHDL',
    useCase: 'Digital hardware design and simulation in Python',
    example: 'Goal: "Design a counter" → Skills: [myhdl_design]',
    prerequisites: ['myhdl'],
    output: 'Hardware module and simulation results',
    category: 'Analysis'
  },
  {
    id: 'riscv_cycle',
    label: 'riscv_cycle',
    desc: 'RISC-V cycle-accurate simulation',
    useCase: 'Detailed RISC-V core simulation at cycle level',
    example: 'Goal: "Simulate RISC-V core" → Skills: [riscv_cycle]',
    prerequisites: ['riscv-pk'],
    output: 'Cycle-accurate trace and stats',
    category: 'Analysis'
  },
  {
    id: 'verilator_sim',
    label: 'verilator_sim',
    desc: 'Verilog simulation with Verilator',
    useCase: 'Fast Verilog/SystemVerilog simulation',
    example: 'Goal: "Simulate this Verilog" → Skills: [verilator_sim]',
    prerequisites: ['verilator'],
    output: 'Simulation waveform and coverage',
    category: 'Analysis'
  },
  {
    id: 'micropython',
    label: 'micropython',
    desc: 'MicroPython for embedded devices',
    useCase: 'Run MicroPython on supported microcontrollers',
    example: 'Goal: "Flash MicroPython" → Skills: [micropython]',
    prerequisites: ['micropython'],
    output: 'Device output and sensor readings',
    category: 'Analysis'
  },
  {
    id: 'platformio',
    label: 'platformio',
    desc: 'Embedded development with PlatformIO',
    useCase: 'Build and upload firmware for embedded boards',
    example: 'Goal: "Build firmware" → Skills: [platformio]',
    prerequisites: ['platformio'],
    output: 'Build artifacts and upload status',
    category: 'Analysis'
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
