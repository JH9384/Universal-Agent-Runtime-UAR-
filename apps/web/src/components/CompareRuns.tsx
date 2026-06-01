import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './CompareRuns.module.css'

interface CompareData {
  run_a: string
  run_b: string
  verdict: string
  status: { a: string | null; b: string | null }
  goal_id: { a: string | null; b: string | null }
  confidence: { a: number | null; b: number | null; delta: number }
  events: { a: number; b: number; delta: number }
  failures: { a: number; b: number; delta: number }
  skills: { a: string[]; b: string[]; added: string[]; removed: string[] }
  failure_skills: { a: string[]; b: string[] }
}

interface CompareRunsProps {
  runA: string
  runB: string
  onClose: () => void
}

function verdictStyle(verdict: string): string {
  const v = verdict.toLowerCase()
  if (v === 'improved') return styles.verdictImproved
  if (v === 'degraded') return styles.verdictDegraded
  if (v === 'mixed') return styles.verdictMixed
  return styles.verdictEquivalent
}

function DeltaBadge({ delta, label }: { delta: number; label: string }) {
  const color =
    delta > 0 ? styles.deltaUp : delta < 0 ? styles.deltaDown : styles.deltaNeutral
  const arrow = delta > 0 ? '▲' : delta < 0 ? '▼' : '—'
  return (
    <span className={`${styles.deltaBadge} ${color}`}>
      {arrow} {Math.abs(delta)} {label}
    </span>
  )
}

function CompareRow({ label, a, b, delta }: { label: string; a: React.ReactNode; b: React.ReactNode; delta: number }) {
  return (
    <div className={styles.compareRow}>
      <div className={styles.compareCell}>
        <span className={styles.compareLabel}>{label}</span>
        <span className={styles.compareValue}>{a}</span>
      </div>
      <div className={styles.compareCell}>
        <span className={styles.compareValue}>{b}</span>
      </div>
      <div className={styles.compareCell}>
        <DeltaBadge delta={delta} label="" />
      </div>
    </div>
  )
}

export function CompareRuns({ runA, runB, onClose }: CompareRunsProps) {
  const [runAInput, setRunAInput] = useState(runA)
  const [runBInput, setRunBInput] = useState(runB)
  const [submitted, setSubmitted] = useState(false)

  const url = submitted
    ? `/api/uar/runs/${encodeURIComponent(runAInput)}/compare/${encodeURIComponent(runBInput)}`
    : null

  const { data, loading, error } = useApiFetch<CompareData>(url || '')

  const handleCompare = () => {
    if (runAInput && runBInput) setSubmitted(true)
  }

  return (
    <div className={styles.compareOverlay} onClick={onClose} role="presentation">
      <div className={styles.comparePanel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.compareHeader}>
          <div>
            <strong>🔍 Compare Runs</strong>
            {data && (
              <span className={`${styles.verdictBadge} ${verdictStyle(data.verdict)}`}>
                {data.verdict}
              </span>
            )}
          </div>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close comparison">✕</button>
        </div>

        {/* Inputs */}
        <div className={styles.compareInputs}>
          <div className={styles.inputGroup}>
            <label className={styles.inputLabel}>Run A</label>
            <input
              className={styles.inputField}
              value={runAInput}
              onChange={(e) => { setRunAInput(e.target.value); setSubmitted(false) }}
              placeholder="Run ID"
            />
          </div>
          <span className={styles.vsLabel}>vs</span>
          <div className={styles.inputGroup}>
            <label className={styles.inputLabel}>Run B</label>
            <input
              className={styles.inputField}
              value={runBInput}
              onChange={(e) => { setRunBInput(e.target.value); setSubmitted(false) }}
              placeholder="Run ID"
            />
          </div>
          <button className={styles.compareButton} onClick={handleCompare}>
            Compare
          </button>
        </div>

        {/* Results */}
        {loading && <div className={styles.loading}>Comparing…</div>}
        {error && <div className={styles.error}>Comparison failed: {error}</div>}

        {data && (
          <div className={styles.compareBody}>
            {/* Summary */}
            <div className={styles.summaryCard}>
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Run A</span>
                <span className={styles.summaryValue}>{data.run_a}</span>
                <span className={styles.statusPill}>{data.status.a || 'unknown'}</span>
              </div>
              <div className={styles.summaryRow}>
                <span className={styles.summaryLabel}>Run B</span>
                <span className={styles.summaryValue}>{data.run_b}</span>
                <span className={styles.statusPill}>{data.status.b || 'unknown'}</span>
              </div>
            </div>

            {/* Metrics */}
            <div className={styles.metricsCard}>
              <h4 className={styles.cardTitle}>Metrics</h4>
              <div className={styles.metricTable}>
                <div className={styles.metricHeader}>
                  <span>Metric</span>
                  <span>Run A</span>
                  <span>Run B</span>
                  <span>Delta</span>
                </div>
                <CompareRow
                  label="Confidence"
                  a={data.confidence.a ?? '—'}
                  b={data.confidence.b ?? '—'}
                  delta={data.confidence.delta}
                />
                <CompareRow
                  label="Events"
                  a={data.events.a}
                  b={data.events.b}
                  delta={data.events.delta}
                />
                <CompareRow
                  label="Failures"
                  a={data.failures.a}
                  b={data.failures.b}
                  delta={data.failures.delta}
                />
              </div>
            </div>

            {/* Skills */}
            <div className={styles.metricsCard}>
              <h4 className={styles.cardTitle}>Skills</h4>
              <div className={styles.skillDiffs}>
                {data.skills.added.length > 0 && (
                  <div className={styles.skillGroup}>
                    <span className={styles.diffLabel}>Added in B</span>
                    <div className={styles.skillChips}>
                      {data.skills.added.map((s) => (
                        <span key={s} className={styles.skillChipAdded}>{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {data.skills.removed.length > 0 && (
                  <div className={styles.skillGroup}>
                    <span className={styles.diffLabel}>Removed in B</span>
                    <div className={styles.skillChips}>
                      {data.skills.removed.map((s) => (
                        <span key={s} className={styles.skillChipRemoved}>{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {data.skills.added.length === 0 && data.skills.removed.length === 0 && (
                  <span className={styles.muted}>No skill changes</span>
                )}
              </div>

              {((data.failure_skills.a?.length || 0) > 0 || (data.failure_skills.b?.length || 0) > 0) && (
                <div className={styles.failureSkills}>
                  <span className={styles.diffLabel}>Failed Skills</span>
                  <div className={styles.failureRow}>
                    <div>
                      <span className={styles.muted}>A:</span>{' '}
                      {data.failure_skills.a.length > 0
                        ? data.failure_skills.a.join(', ')
                        : <span className={styles.muted}>None</span>}
                    </div>
                    <div>
                      <span className={styles.muted}>B:</span>{' '}
                      {data.failure_skills.b.length > 0
                        ? data.failure_skills.b.join(', ')
                        : <span className={styles.muted}>None</span>}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
