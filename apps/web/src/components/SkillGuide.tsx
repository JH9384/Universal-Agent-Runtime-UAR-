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
  category: 'Core' | 'AI' | 'GraphRAG' | 'Storage' | 'Analysis'
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
  }
]

const CATEGORIES = ['Core', 'AI', 'GraphRAG', 'Storage', 'Analysis'] as const

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
