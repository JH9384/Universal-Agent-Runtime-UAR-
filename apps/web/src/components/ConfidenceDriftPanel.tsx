import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './ConfidenceDriftPanel.module.css'

interface Contributor {
  name: string
  impact: number
  type: string
}

interface DriftData {
  window_hours: number
  current_score: number | null
  window_start_score: number | null
  delta: number
  state: string
  confidence_history: number[]
  top_contributors: Contributor[]
  failure_summary: {
    total_failures: number
    top_skills: { skill: string; count: number }[]
  }
}

function stateClass(state: string): string {
  const s = state.toLowerCase()
  if (s === 'improving') return styles.stateImproving
  if (s === 'degrading') return styles.stateDegrading
  return styles.stateStable
}

function MiniSparkline({ data }: { data: number[] }) {
  if (data.length < 2) {
    return <div className={styles.sparklineEmpty}>Not enough data</div>
  }
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 200
    const y = 36 - ((v - min) / range) * 30 - 3
    return [x, y]
  })
  const d = points.reduce(
    (acc, [x, y], i) => acc + (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`),
    ''
  )
  return (
    <svg width="100%" height={40} viewBox="0 0 200 40" className={styles.sparkline}>
      <path d={d} fill="none" stroke="#2980b9" strokeWidth={2} />
      <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r={3} fill="#2980b9" />
    </svg>
  )
}

export function ConfidenceDriftPanel() {
  const { data, loading, error } = useApiFetch<DriftData>(
    '/api/uar/confidence-drift?hours=24',
    { interval: 30_000 }
  )

  const history = data?.confidence_history || []

  if (loading) return <div className={styles.loading}>Loading drift…</div>
  if (error) return <div className={styles.error}>Drift failed: {error}</div>

  return (
    <div className={styles.driftPanel}>
      <div className={styles.driftHeader}>
        <h4 className={styles.panelTitle}>Confidence Drift</h4>
        {data && (
          <span className={`${styles.stateBadge} ${stateClass(data.state)}`}>
            {data.state}
          </span>
        )}
      </div>

      <p className={styles.panelDesc}>
        {data?.window_hours ?? 24}h window · {history.length} data points
      </p>

      {/* Score row */}
      {data && (
        <div className={styles.scoreRow}>
          <div className={styles.scoreBlock}>
            <span className={styles.scoreLabel}>Previous</span>
            <span className={styles.scoreValue}>{data.window_start_score ?? '—'}</span>
          </div>
          <div className={styles.scoreBlock}>
            <span className={styles.scoreLabel}>Current</span>
            <span className={styles.scoreValue}>{data.current_score ?? '—'}</span>
          </div>
          <div className={styles.scoreBlock}>
            <span className={styles.scoreLabel}>Delta</span>
            <span className={`${styles.scoreValue} ${data.delta > 0 ? styles.positive : data.delta < 0 ? styles.negative : ''}`}>
              {data.delta > 0 ? '+' : ''}{data.delta}
            </span>
          </div>
        </div>
      )}

      {/* Sparkline */}
      {history.length >= 2 && (
        <div className={styles.sparklineWrap}>
          <MiniSparkline data={history} />
        </div>
      )}

      {/* Contributors */}
      {data && data.top_contributors.length > 0 && (
        <div className={styles.contributorsSection}>
          <h5 className={styles.sectionTitle}>Top Contributors</h5>
          <div className={styles.contributorList}>
            {data.top_contributors.map((c) => (
              <div key={c.name} className={styles.contributorRow}>
                <span className={styles.contributorName}>{c.name}</span>
                <span className={`${styles.contributorImpact} ${c.impact < 0 ? styles.negative : c.impact > 0 ? styles.positive : ''}`}>
                  {c.impact > 0 ? '+' : ''}{c.impact}
                </span>
                <span className={styles.contributorType}>{c.type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failure correlation */}
      {data && data.failure_summary.total_failures > 0 && (
        <div className={styles.contributorsSection}>
          <h5 className={styles.sectionTitle}>
            Failures ({data.failure_summary.total_failures})
          </h5>
          <div className={styles.failureList}>
            {data.failure_summary.top_skills.map((s) => (
              <span key={s.skill} className={styles.failureChip}>
                {s.skill}: {s.count}
              </span>
            ))}
          </div>
        </div>
      )}

      {(!data || history.length < 2) && (
        <div className={styles.emptyState}>
          Not enough confidence history to compute drift.
          History builds as Mission Control snapshots are collected.
        </div>
      )}
    </div>
  )
}
