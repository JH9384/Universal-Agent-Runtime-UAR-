import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './ReportViewer.module.css'

interface TrustReport {
  report_type: string
  generated_at: number
  narrative: string
  trust_distribution: Record<string, number>
  drift_signals: { type: string; penalty: number }[]
  outcome_correlation: number | null
  type_count: number
  system_calibration_error: number | null
}

interface BurninReport {
  report_type: string
  generated_at: number
  narrative: string
  snapshot_count: number
  trust_stable: boolean | null
  recommendation_growth: number | null
  latest_recommendation_count: number
  earliest_recommendation_count: number
}

export function ReportViewer() {
  const [tab, setTab] = useState<'trust' | 'burnin'>('trust')
  const { data: trustData, loading: tL, error: tE } =
    useApiFetch<TrustReport>('/api/uar/reports/trust-validation')
  const { data: burninData, loading: bL, error: bE } =
    useApiFetch<BurninReport>('/api/uar/reports/burnin-24h')

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Report Viewer</h4>
        <div className={styles.tabs}>
          <button className={`${styles.tab} ${tab === 'trust' ? styles.tabActive : ''}`} onClick={() => setTab('trust')}>Trust Validation</button>
          <button className={`${styles.tab} ${tab === 'burnin' ? styles.tabActive : ''}`} onClick={() => setTab('burnin')}>24h Burn-In</button>
        </div>
      </div>

      {tab === 'trust' && (
        <div className={styles.reportBody}>
          {tL && <div className={styles.loading}>Loading…</div>}
          {tE && <div className={styles.error}>{tE}</div>}
          {trustData && (
            <>
              <div className={styles.narrative}>{trustData.narrative}</div>
              <div className={styles.statGrid}>
                <StatBox label="Types" value={trustData.type_count} />
                <StatBox label="Correlation" value={trustData.outcome_correlation ?? '—'} />
                <StatBox label="Calibration" value={trustData.system_calibration_error?.toFixed(3) ?? '—'} />
              </div>
              <h5 className={styles.sectionTitle}>Trust Distribution</h5>
              {Object.entries(trustData.trust_distribution).map(([band, count]) => (
                <DistRow key={band} band={band} count={count} />
              ))}
              {trustData.drift_signals.length > 0 && (
                <>
                  <h5 className={styles.sectionTitle}>Drift Signals</h5>
                  {trustData.drift_signals.map((d) => (
                    <div key={d.type} className={styles.driftRow}>
                      <span>{d.type}</span>
                      <span className={styles.driftPenalty}>-{d.penalty}</span>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}

      {tab === 'burnin' && (
        <div className={styles.reportBody}>
          {bL && <div className={styles.loading}>Loading…</div>}
          {bE && <div className={styles.error}>{bE}</div>}
          {burninData && (
            <>
              <div className={styles.narrative}>{burninData.narrative}</div>
              <div className={styles.statGrid}>
                <StatBox label="Snapshots" value={burninData.snapshot_count} />
                <StatBox label="Growth" value={burninData.recommendation_growth ?? '—'} />
                <StatBox label="Latest Count" value={burninData.latest_recommendation_count} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.statBox}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

function DistRow({ band, count }: { band: string; count: number }) {
  return (
    <div className={styles.distRow}>
      <span className={styles.distLabel}>{band.replace('_', ' ')}</span>
      <div className={styles.distBarWrap}>
        <div className={styles.distBar} style={{ width: `${Math.min(100, count * 20)}%` }} />
      </div>
      <span className={styles.distCount}>{count}</span>
    </div>
  )
}
