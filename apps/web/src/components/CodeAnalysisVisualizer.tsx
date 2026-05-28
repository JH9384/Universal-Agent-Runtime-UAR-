import { useState, useCallback } from 'react'
import styles from './MathVisualizer.module.css'

interface Issue {
  type: string
  message: string
  line?: number
}

interface CodeAnalysisData {
  status: string
  result?: {
    language: string
    lines: { total: number; blank: number; comment: number; code: number }
    functions: string[]
    classes: string[]
    imports: string[]
    complexity: { decision_points: number; function_count: number; estimated_complexity: number }
    issues: Issue[]
  }
  metrics?: {
    total_lines: number
    code_lines: number
    function_count: number
    class_count: number
    import_count: number
    issue_count: number
  }
  error?: string
}

interface CodeAnalysisVisualizerProps {
  data: CodeAnalysisData | null
  darkMode?: boolean
}

export function CodeAnalysisVisualizer({ data, darkMode = false }: CodeAnalysisVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'functions' | 'issues'>('overview')

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(() => {})
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the code_analysis skill to generate results.</p>
        </div>
      </div>
    )
  }

  if (data.error || data.status === 'failed') {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>Code Analysis</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error || 'Analysis failed'}</p>
        </div>
      </div>
    )
  }

  const result = data.result
  const metrics = data.metrics

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          Code Analysis{result?.language ? ` (${result.language})` : ''}
        </span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'overview' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'functions' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('functions')}
          >
            Functions
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'issues' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('issues')}
          >
            Issues{metrics?.issue_count ? ` (${metrics.issue_count})` : ''}
          </button>
          <button className={styles.toolbarButton} onClick={handleCopy} title="Copy JSON">
            📋
          </button>
        </div>
      </div>

      {activeTab === 'overview' && result && (
        <div className={styles.scrollContent}>
          <div className={styles.infoGrid} style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '16px' }}>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{metrics?.total_lines ?? result.lines.total}</div>
              <div className={styles.infoLabel}>Total Lines</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{metrics?.code_lines ?? result.lines.code}</div>
              <div className={styles.infoLabel}>Code Lines</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{result.lines.comment}</div>
              <div className={styles.infoLabel}>Comments</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{result.lines.blank}</div>
              <div className={styles.infoLabel}>Blank</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{metrics?.function_count ?? result.functions.length}</div>
              <div className={styles.infoLabel}>Functions</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{metrics?.class_count ?? result.classes.length}</div>
              <div className={styles.infoLabel}>Classes</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{metrics?.import_count ?? result.imports.length}</div>
              <div className={styles.infoLabel}>Imports</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{result.complexity.estimated_complexity}</div>
              <div className={styles.infoLabel}>Complexity</div>
            </div>
          </div>

          {result.imports.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h4 className={styles.sectionTitle}>Imports / Modules</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {result.imports.map((imp, i) => (
                  <span key={i} className={styles.chip}>
                    {imp}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'functions' && result && (
        <div className={styles.scrollContent}>
          {result.functions.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h4 className={styles.sectionTitle}>Functions ({result.functions.length})</h4>
              <ul style={{ margin: 0, padding: '0 0 0 16px' }}>
                {result.functions.map((fn, i) => (
                  <li key={i} style={{ marginBottom: '2px' }}><code>{fn}()</code></li>
                ))}
              </ul>
            </div>
          )}
          {result.classes.length > 0 && (
            <div>
              <h4 className={styles.sectionTitle}>Classes ({result.classes.length})</h4>
              <ul style={{ margin: 0, padding: '0 0 0 16px' }}>
                {result.classes.map((cls, i) => (
                  <li key={i} style={{ marginBottom: '2px' }}><code>{cls}</code></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {activeTab === 'issues' && result && (
        <div className={styles.scrollContent}>
          {result.issues.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#22c55e' }}>
              No issues found
            </div>
          ) : (
            <div>
              {result.issues.map((issue, i) => (
                <div
                  key={i}
                  style={{
                    padding: '8px 12px',
                    marginBottom: '6px',
                    borderRadius: '4px',
                    background: issue.type === 'error' || issue.type === 'bare_except' ? '#fee' : '#fef3c7',
                    border: `1px solid ${issue.type === 'error' || issue.type === 'bare_except' ? '#fcc' : '#fcd34d'}`,
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '2px' }}>
                    {issue.type}
                  </div>
                  <div style={{ fontSize: '13px' }}>{issue.message}</div>
                  {issue.line && (
                    <div style={{ fontSize: '11px', color: '#888', marginTop: '2px' }}>
                      Line {issue.line}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
