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
  summary?: {
    cache_consistency_violations?: number | null
    cache_consistency_violation_rate?: number | null
    avg_cache_consistency_score?: number | null
    metadata_key_count_end?: number | null
    metadata_key_growth?: number | null
    avg_metadata_scan_latency_ms?: number | null
    snapshot_count_end?: number | null
    snapshot_growth?: number | null
    expected_snapshots?: number | null
    avg_snapshot_retrieval_latency_ms?: number | null
    avg_trust_report_duration_ms?: number | null
    avg_burnin_report_duration_ms?: number | null
    graph_node_count_end?: number | null
    graph_edge_count_end?: number | null
    avg_graph_generation_time_ms?: number | null
  }
  sample_count?: number
  duration_hours?: number
}

export function ReportViewer() {
  const [tab, setTab] = useState<'trust' | 'burnin'>('trust')
  const { data: trustData, loading: tL, error: tE } =
    useApiFetch<TrustReport>('/api/uar/reports/trust-validation')
  const { data: burninData, loading: bL, error: bE } =
    useApiFetch<BurninReport>('/api/uar/reports/burnin-24h')

  const maxDist = trustData
    ? Math.max(1, ...Object.values(trustData.trust_distribution))
    : 1

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
                <DistRow key={band} band={band} count={count} max={maxDist} />
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
                <StatBox label="Snapshots" value={burninData.summary?.snapshot_count_end ?? burninData.snapshot_count} />
                <StatBox label="Samples" value={burninData.sample_count ?? '—'} />
                <StatBox label="Duration" value={burninData.duration_hours != null ? `${burninData.duration_hours}h` : '—'} />
                <StatBox label="Rec Growth" value={burninData.recommendation_growth ?? '—'} />
                <StatBox label="Trust Stable" value={burninData.trust_stable == null ? '—' : burninData.trust_stable ? 'Yes' : 'No'} />
              </div>
              {burninData.summary && (
                <>
                  <h5 className={styles.sectionTitle}>Cache Consistency</h5>
                  <div className={styles.statGrid}>
                    <StatBox label="Violations" value={burninData.summary.cache_consistency_violations ?? '—'} />
                    <StatBox label="Rate" value={burninData.summary.cache_consistency_violation_rate != null ? `${(burninData.summary.cache_consistency_violation_rate * 100).toFixed(1)}%` : '—'} />
                    <StatBox label="Avg Δ" value={burninData.summary.avg_cache_consistency_score?.toFixed(4) ?? '—'} />
                  </div>
                  <h5 className={styles.sectionTitle}>Metadata &amp; Snapshots</h5>
                  <div className={styles.statGrid}>
                    <StatBox label="Meta Keys" value={burninData.summary.metadata_key_count_end ?? '—'} />
                    <StatBox label="Key Growth" value={burninData.summary.metadata_key_growth ?? '—'} />
                    <StatBox label="Scan Avg" value={burninData.summary.avg_metadata_scan_latency_ms != null ? `${burninData.summary.avg_metadata_scan_latency_ms.toFixed(1)}ms` : '—'} />
                    <StatBox label="Snap Growth" value={burninData.summary.snapshot_growth ?? '—'} />
                    <StatBox label="Ret Avg" value={burninData.summary.avg_snapshot_retrieval_latency_ms != null ? `${burninData.summary.avg_snapshot_retrieval_latency_ms.toFixed(1)}ms` : '—'} />
                  </div>
                  <h5 className={styles.sectionTitle}>Report Timing</h5>
                  <div className={styles.statGrid}>
                    <StatBox label="Trust Avg" value={burninData.summary.avg_trust_report_duration_ms != null ? `${burninData.summary.avg_trust_report_duration_ms.toFixed(0)}ms` : '—'} />
                    <StatBox label="Burn-In Avg" value={burninData.summary.avg_burnin_report_duration_ms != null ? `${burninData.summary.avg_burnin_report_duration_ms.toFixed(0)}ms` : '—'} />
                  </div>
                  <h5 className={styles.sectionTitle}>Knowledge Graph</h5>
                  <div className={styles.statGrid}>
                    <StatBox label="Nodes" value={burninData.summary.graph_node_count_end ?? '—'} />
                    <StatBox label="Edges" value={burninData.summary.graph_edge_count_end ?? '—'} />
                    <StatBox label="Gen Avg" value={burninData.summary.avg_graph_generation_time_ms != null ? `${burninData.summary.avg_graph_generation_time_ms.toFixed(0)}ms` : '—'} />
                  </div>
                </>
              )}
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

function DistRow({ band, count, max }: { band: string; count: number; max: number }) {
  return (
    <div className={styles.distRow}>
      <span className={styles.distLabel}>{band.replaceAll('_', ' ')}</span>
      <div className={styles.distBarWrap}>
        <div className={styles.distBar} style={{ width: `${Math.round((count / max) * 100)}%` }} />
      </div>
      <span className={styles.distCount}>{count}</span>
    </div>
  )
}
