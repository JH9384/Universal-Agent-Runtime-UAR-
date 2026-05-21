import { useState, useCallback } from 'react'
import styles from './MathVisualizer.module.css'

interface MathData {
  success: boolean
  operation?: string
  expression?: string
  variable?: string
  status?: string
  result?: string
  result_latex?: string
  result_type?: string
  solutions?: string[]
  solution_count?: number
  derivative?: string
  derivative_latex?: string
  integral?: string
  integral_latex?: string
  original?: string
  simplified?: string
  simplified_latex?: string
  error?: string
}

interface MathVisualizerProps {
  data: MathData | null
  darkMode?: boolean
}

function EquationBlock({ label, latex, plain }: { label: string; latex?: string; plain?: string }) {
  const display = latex || plain || ''
  if (!display) return null
  return (
    <div className={styles.equationBlock}>
      <span className={styles.eqLabel}>{label}</span>
      <code className={styles.eqCode}>{display}</code>
    </div>
  )
}

function SolutionList({ solutions }: { solutions?: string[] }) {
  if (!solutions || solutions.length === 0) return null
  return (
    <div className={styles.solutionList}>
      <span className={styles.eqLabel}>Solutions</span>
      {solutions.map((sol, i) => (
        <div key={i} className={styles.solutionItem}>
          <span className={styles.solutionIndex}>{i + 1}.</span>
          <code className={styles.eqCode}>{sol}</code>
        </div>
      ))}
    </div>
  )
}

export function MathVisualizer({ data, darkMode = false }: MathVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'math' | 'raw'>('math')

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(() => {})
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the math_compute skill to generate computation results.</p>
        </div>
      </div>
    )
  }

  const op = data.operation || 'evaluate'
  const expr = data.expression || ''

  if (!data.success) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>Math Computation</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error || 'Computation failed'}</p>
          {expr && <code className={styles.errorExpr}>{expr}</code>}
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Math: {op.charAt(0).toUpperCase() + op.slice(1)}</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'math' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('math')}
          >
            Math
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
          <button className={styles.toolbarButton} onClick={handleCopy} title="Copy JSON">
            📋
          </button>
        </div>
      </div>

      {activeTab === 'math' ? (
        <div className={styles.scrollContent}>
          {/* Expression */}
          {expr && (
            <div className={styles.exprHeader}>
              <span className={styles.exprLabel}>Expression</span>
              <code className={styles.exprCode}>{expr}</code>
              {data.variable && (
                <span className={styles.exprMeta}>Variable: {data.variable}</span>
              )}
            </div>
          )}

          {/* Operation-specific results */}
          {op === 'solve' && (
            <div className={styles.resultSection}>
              <h4 className={styles.sectionTitle}>Solutions</h4>
              <SolutionList solutions={data.solutions} />
              {data.solution_count !== undefined && (
                <span className={styles.metaText}>{data.solution_count} solution(s) found</span>
              )}
            </div>
          )}

          {op === 'differentiate' && (
            <div className={styles.resultSection}>
              <h4 className={styles.sectionTitle}>Derivative</h4>
              <EquationBlock label="d/dx" latex={data.derivative_latex} plain={data.derivative} />
            </div>
          )}

          {op === 'integrate' && (
            <div className={styles.resultSection}>
              <h4 className={styles.sectionTitle}>Integral</h4>
              <EquationBlock label="∫" latex={data.integral_latex} plain={data.integral} />
            </div>
          )}

          {op === 'simplify' && (
            <div className={styles.resultSection}>
              <h4 className={styles.sectionTitle}>Simplification</h4>
              <EquationBlock label="Original" plain={data.original} />
              <EquationBlock label="Simplified" latex={data.simplified_latex} plain={data.simplified} />
            </div>
          )}

          {op === 'evaluate' && (
            <div className={styles.resultSection}>
              <h4 className={styles.sectionTitle}>Result</h4>
              <EquationBlock label="Value" latex={data.result_latex} plain={data.result} />
              {data.result_type && (
                <span className={styles.metaText}>Type: {data.result_type}</span>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className={styles.rawPanel}>
          <pre className={styles.rawCode}>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
