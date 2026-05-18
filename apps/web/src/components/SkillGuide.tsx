import { useState } from 'react'

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
    <div style={{ padding: 20, fontFamily: 'system-ui, sans-serif' }}>
      <h3 style={{ margin: '0 0 16px 0' }}>📘 Skill Guide</h3>

      {/* Category Filter */}
      <div style={{ marginBottom: 16 }}>
        <span style={{ fontSize: 12, color: '#666', marginRight: 8 }}>Filter:</span>
        <button
          onClick={() => setFilterCategory('All')}
          style={{
            padding: '4px 10px',
            margin: '2px',
            border: '1px solid #ccc',
            borderRadius: 4,
            background: filterCategory === 'All' ? '#e7f1ff' : '#fff',
            cursor: 'pointer'
          }}
        >
          All
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setFilterCategory(cat)}
            style={{
              padding: '4px 10px',
              margin: '2px',
              border: '1px solid #ccc',
              borderRadius: 4,
              background: filterCategory === cat ? '#e7f1ff' : '#fff',
              cursor: 'pointer'
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Skill List */}
      <div style={{ display: 'grid', gap: 8 }}>
        {filteredSkills.map(skill => (
          <div
            key={skill.id}
            onClick={() => setSelectedSkill(skill)}
            style={{
              padding: 12,
              border: '1px solid #dee2e6',
              borderRadius: 6,
              cursor: 'pointer',
              background: '#fff',
              transition: 'all 0.15s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#f8f9fa'}
            onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <strong style={{ fontFamily: 'monospace' }}>{skill.label}</strong>
              <span style={{
                fontSize: 11,
                padding: '2px 6px',
                background: '#e9ecef',
                borderRadius: 4,
                color: '#495057'
              }}>
                {skill.category}
              </span>
            </div>
            <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
              {skill.desc}
            </div>
          </div>
        ))}
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <div
          onClick={() => setSelectedSkill(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
        >
          <div
            onClick={(e: any) => e.stopPropagation()}
            style={{
              width: 'min(600px, 90vw)',
              maxHeight: '80vh',
              background: '#fff',
              borderRadius: 8,
              padding: 20,
              overflow: 'auto',
              boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h4 style={{ margin: 0, fontFamily: 'monospace' }}>{selectedSkill.label}</h4>
              <button
                onClick={() => setSelectedSkill(null)}
                style={{ padding: '4px 10px', border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ marginBottom: 12 }}>
              <span style={{
                fontSize: 11,
                padding: '4px 8px',
                background: '#e9ecef',
                borderRadius: 4,
                color: '#495057'
              }}>
                {selectedSkill.category}
              </span>
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 12, color: '#555' }}>Description:</strong>
              <div style={{ fontSize: 14, marginTop: 4 }}>{selectedSkill.desc}</div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 12, color: '#555' }}>When to use:</strong>
              <div style={{ fontSize: 14, marginTop: 4 }}>{selectedSkill.useCase}</div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong style={{ fontSize: 12, color: '#555' }}>Example:</strong>
              <div style={{
                fontSize: 13,
                marginTop: 4,
                padding: 8,
                background: '#f8f9fa',
                borderRadius: 4,
                fontFamily: 'monospace'
              }}>
                {selectedSkill.example}
              </div>
            </div>

            {selectedSkill.prerequisites && (
              <div style={{ marginBottom: 12 }}>
                <strong style={{ fontSize: 12, color: '#555' }}>Prerequisites:</strong>
                <div style={{ marginTop: 4 }}>
                  {selectedSkill.prerequisites.map(prereq => (
                    <span
                      key={prereq}
                      style={{
                        display: 'inline-block',
                        fontSize: 11,
                        padding: '2px 8px',
                        margin: '2px',
                        background: '#fff3cd',
                        border: '1px solid #ffc107',
                        borderRadius: 4,
                        color: '#856404'
                      }}
                    >
                      {prereq}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <strong style={{ fontSize: 12, color: '#555' }}>Output:</strong>
              <div style={{ fontSize: 14, marginTop: 4 }}>{selectedSkill.output}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
