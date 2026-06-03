import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './TrustExplorer.module.css'

interface TrustTypeData {
  type: string
  trust_score: number
  effectiveness_component: number
  calibration_component: number
  evidence_component: number
  drift_penalty: number
}

interface TrustResponse {
  generated_at: number
  system_calibration_error: number
  recommendation_types: TrustTypeData[]
}

interface ExplorerDetail {
  type: string
  trust_score: number
  effectiveness: {
    score: number
    resolved: number
    total: number
    drift_penalty: number
  }
  calibration: {
    score: number
    error: number
    bucket: string
  }
  evidence: {
    score: number
    sample_size: number
    resolution_rate: number
  }
  generated_at: number
}

function trustBandClass(score: number): string {
  if (score >= 0.80) return styles.bandHigh
  if (score >= 0.60) return styles.bandTrusted
  if (score >= 0.40) return styles.bandWatch
  if (score >= 0.20) return styles.bandWeak
  return styles.bandUntrusted
}

function trustBandLabel(score: number): string {
  if (score >= 0.80) return 'Highly Trusted'
  if (score >= 0.60) return 'Trusted'
  if (score >= 0.40) return 'Watch'
  if (score >= 0.20) return 'Weak'
  return 'Untrusted'
}

export function TrustExplorer() {
  const { data, loading, error } = useApiFetch<TrustResponse>(
    '/api/uar/recommendations/trust'
  )
  const [selected, setSelected] = useState<string | null>(null)
  const [detailUrl, setDetailUrl] = useState<string | null>(null)

  const handleSelect = (type: string) => {
    setSelected(type)
    setDetailUrl(`/api/uar/trust-explorer/${encodeURIComponent(type)}`)
  }

  const { data: detail, loading: detailLoading } =
    useApiFetch<ExplorerDetail>(detailUrl || '')

  if (loading) return <div className={styles.loading}>Loading trust…</div>
  if (error) return <div className={styles.error}>Trust failed: {error}</div>
  if (!data || data.recommendation_types.length === 0) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.panelTitle}>Trust Explorer</h4>
        <div className={styles.emptyState}>No trust data available yet.</div>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Trust Explorer</h4>
      <p className={styles.subtitle}>
        Click any type to see why it scored that way.
      </p>

      <div className={styles.typeGrid}>
        {data.recommendation_types.map((t) => (
          <button
            key={t.type}
            className={`${styles.typeCard} ${trustBandClass(t.trust_score)} ${selected === t.type ? styles.selected : ''}`}
            onClick={() => handleSelect(t.type)}
          >
            <div className={styles.typeHeader}>
              <span className={styles.typeName}>{t.type}</span>
              <span className={styles.bandLabel}>
                {trustBandLabel(t.trust_score)}
              </span>
            </div>
            <div className={styles.scoreRow}>
              <span className={styles.scoreValue}>
                {t.trust_score.toFixed(2)}
              </span>
              {t.drift_penalty > 0 && (
                <span className={styles.driftBadge}>
                  -{t.drift_penalty}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>

      {selected && detail && !detailLoading && (
        <div className={styles.detailPanel}>
          <h5 className={styles.detailTitle}>
            {selected} — {trustBandLabel(detail.trust_score)}
          </h5>

          <ComponentRow
            label="Effectiveness"
            score={detail.effectiveness.score}
            detail={`${detail.effectiveness.resolved}/${detail.effectiveness.total} resolved`}
            color={styles.barEffectiveness}
          />
          <ComponentRow
            label="Calibration"
            score={detail.calibration.score}
            detail={`Error ${detail.calibration.error.toFixed(3)} · ${detail.calibration.bucket}`}
            color={styles.barCalibration}
          />
          <ComponentRow
            label="Evidence"
            score={detail.evidence.score}
            detail={`${detail.evidence.sample_size} samples · ${(detail.evidence.resolution_rate * 100).toFixed(0)}% resolved`}
            color={styles.barEvidence}
          />

          {detail.effectiveness.drift_penalty > 0 && (
            <div className={styles.driftWarning}>
              Drift penalty: -{detail.effectiveness.drift_penalty}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ComponentRow({
  label,
  score,
  detail,
  color,
}: {
  label: string
  score: number
  detail: string
  color: string
}) {
  const pct = Math.max(0, Math.min(100, (score || 0) * 100))
  return (
    <div className={styles.componentRow}>
      <div className={styles.componentHeader}>
        <span className={styles.componentLabel}>{label}</span>
        <span className={styles.componentScore}>
          {(score || 0).toFixed(2)}
        </span>
      </div>
      <div className={styles.componentBar}>
        <div
          className={`${styles.componentFill} ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className={styles.componentDetail}>{detail}</div>
    </div>
  )
}
