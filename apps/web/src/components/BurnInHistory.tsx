import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './BurnInHistory.module.css'

interface BurnInReport {
  timestamp: number
  score: number
  passed: boolean
  level: string
  evidence: { scenario: string; passed: boolean; score: number }[]
  errors: string[]
}

interface BurnInHistoryResponse {
  limit: number
  total: number
  pass_rate: number
  average_score: number
  reports: BurnInReport[]
}

function MiniBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={styles.miniBarTrack}>
      <div className={styles.miniBarFill} style={{ ['--fill-width' as string]: `${pct}%` }} />
    </div>
  )
}

export function BurnInHistory() {
  const { data, loading, error } = useApiFetch<BurnInHistoryResponse>(
    '/api/uar/burnin/history?limit=20'
  )

  const reports = data?.reports || []

  const scoreSeries = useMemo(
    () => reports.map((r) => r.score).filter((v) => typeof v === 'number'),
    [reports]
  )

  if (loading) return <div className={styles.loading}>Loading burn-in history…</div>
  if (error) return <div className={styles.error}>History failed: {error}</div>

  return (
    <div className={styles.burnInHistory}>
      <h4 className={styles.panelTitle}>Burn-In History</h4>
      <p className={styles.panelDesc}>
        {data?.total ?? 0} run{data?.total !== 1 ? 's' : ''} recorded · Pass rate:{' '}
        {data?.pass_rate != null ? `${Math.round(data.pass_rate * 100)}%` : '—'} · Avg score:{' '}
        {data?.average_score ?? '—'}
      </p>

      {/* Score trend sparkline */}
      {scoreSeries.length >= 2 && (
        <div className={styles.sparklineWrap}>
          <svg width="100%" height={40} className={styles.sparkline}>
            {scoreSeries.map((score, i) => {
              const x = (i / (scoreSeries.length - 1)) * 240
              const y = 40 - (score / 100) * 36 - 2
              const isPass = score >= 80
              return (
                <g key={i}>
                  <line
                    x1={x}
                    y1={y}
                    y2={40}
                    className={isPass ? styles.barPass : styles.barFail}
                    strokeWidth={4}
                  />
                  <circle
                    cx={x}
                    cy={y}
                    r={3}
                    className={isPass ? styles.dotPass : styles.dotFail}
                  />
                </g>
              )
            })}
          </svg>
        </div>
      )}

      {/* Report list */}
      <div className={styles.reportList}>
        {reports.length === 0 ? (
          <div className={styles.emptyState}>
            No burn-in runs recorded yet. Trigger a burn-in run to build history.
          </div>
        ) : (
          reports.map((report, i) => (
            <div
              key={i}
              className={`${styles.reportCard} ${report.passed ? styles.reportPass : styles.reportFail}`}
            >
              <div className={styles.reportHeader}>
                <span className={styles.reportTime}>
                  {new Date(report.timestamp * 1000).toLocaleString()}
                </span>
                <span
                  className={`${styles.badge} ${report.passed ? styles.badgePass : styles.badgeFail}`}
                >
                  {report.passed ? 'Pass' : 'Fail'}
                </span>
              </div>

              <div className={styles.reportBody}>
                <div className={styles.scoreRow}>
                  <span className={styles.scoreLabel}>Score</span>
                  <span className={styles.scoreValue}>{report.score}</span>
                  <MiniBar value={report.score} />
                </div>
                <div className={styles.metaRow}>
                  <span className={styles.metaItem}>
                    {report.evidence?.length ?? 0} scenarios
                  </span>
                  <span className={styles.metaItem}>
                    {report.errors?.length ?? 0} errors
                  </span>
                  <span className={styles.metaItem}>Level: {report.level}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
