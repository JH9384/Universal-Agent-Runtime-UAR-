import { useApiFetch } from '../hooks/useApiFetch'
import styles from './TrustTrendPanel.module.css'

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
  system_calibration_error: number | null
  recommendation_types: TrustTypeData[]
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

export function TrustTrendPanel() {
  const { data, loading, error } = useApiFetch<TrustResponse>(
    '/api/uar/recommendations/trust',
    { interval: 30_000 }
  )

  if (loading) return <div className={styles.loading}>Loading trust data…</div>
  if (error) return <div className={styles.error}>Trust data failed: {error}</div>
  if (!data || data.recommendation_types.length === 0) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.panelTitle}>Trust Trends</h4>
        <div className={styles.emptyState}>No trust data available yet.</div>
      </div>
    )
  }

  const types = data.recommendation_types
  const avgTrust = types.reduce((sum, t) => sum + t.trust_score, 0) / types.length
  const driftCount = types.filter((t) => t.drift_penalty > 0).length

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h4 className={styles.panelTitle}>Trust Distribution</h4>
        <span className={styles.meta}>
          {types.length} types · Avg {avgTrust.toFixed(2)}
        </span>
      </div>

      {driftCount > 0 && (
        <div className={styles.driftAlert}>
          {driftCount} type(s) showing drift signals
        </div>
      )}

      <div className={styles.typeList}>
        {types.map((t) => (
          <div key={t.type} className={`${styles.typeRow} ${trustBandClass(t.trust_score)}`}>
            <div className={styles.typeHeader}>
              <span className={styles.typeName}>{t.type}</span>
              <span className={styles.bandLabel}>{trustBandLabel(t.trust_score)}</span>
              <span className={styles.trustScore}>{t.trust_score.toFixed(2)}</span>
            </div>
            <div className={styles.componentBar}>
              <div
                className={`${styles.componentSegment} ${styles.componentEffectiveness}`}
                style={{ width: `${t.effectiveness_component * 100}%` }}
                title={`Effectiveness: ${t.effectiveness_component.toFixed(2)}`}
              />
              <div
                className={`${styles.componentSegment} ${styles.componentCalibration}`}
                style={{ width: `${t.calibration_component * 100}%` }}
                title={`Calibration: ${t.calibration_component.toFixed(2)}`}
              />
              <div
                className={`${styles.componentSegment} ${styles.componentEvidence}`}
                style={{ width: `${t.evidence_component * 100}%` }}
                title={`Evidence: ${t.evidence_component.toFixed(2)}`}
              />
            </div>
            <div className={styles.componentLegend}>
              <span className={styles.legendItem}>
                <span className={`${styles.legendDot} ${styles.componentEffectiveness}`} />
                Eff {t.effectiveness_component.toFixed(2)}
              </span>
              <span className={styles.legendItem}>
                <span className={`${styles.legendDot} ${styles.componentCalibration}`} />
                Cal {t.calibration_component.toFixed(2)}
              </span>
              <span className={styles.legendItem}>
                <span className={`${styles.legendDot} ${styles.componentEvidence}`} />
                Evi {t.evidence_component.toFixed(2)}
              </span>
              {t.drift_penalty > 0 && (
                <span className={`${styles.legendItem} ${styles.driftItem}`}>
                  <span className={`${styles.legendDot} ${styles.componentDrift}`} />
                  Drift -{t.drift_penalty.toFixed(2)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.footer}>
        <span className={styles.footerLabel}>System Calibration Error:</span>
        <span className={styles.footerValue}>
          {data.system_calibration_error?.toFixed(3) ?? '—'}
        </span>
      </div>
    </div>
  )
}
