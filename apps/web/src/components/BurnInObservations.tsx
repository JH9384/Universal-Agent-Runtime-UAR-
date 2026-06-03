import { useApiFetch } from '../hooks/useApiFetch'
import styles from './BurnInObservations.module.css'

interface BurninSample {
  timestamp: number
  cache_consistency_score: number | null
  cache_consistency_ok: boolean | null
  metadata_key_count: number | null
  metadata_scan_latency_ms: number | null
  snapshot_count: number | null
  snapshot_retrieval_latency_ms: number | null
  trust_report_duration_ms: number | null
  burnin_report_duration_ms: number | null
  graph_node_count: number | null
  graph_edge_count: number | null
  graph_generation_time_ms: number | null
}

interface BurninObsReport {
  summary: {
    cache_consistency_violations: number | null
    cache_consistency_violation_rate: number | null
    avg_cache_consistency_score: number | null
    max_cache_consistency_score: number | null
    metadata_key_count_start: number | null
    metadata_key_count_end: number | null
    metadata_key_growth: number | null
    avg_metadata_scan_latency_ms: number | null
    max_metadata_scan_latency_ms: number | null
    snapshot_count_start: number | null
    snapshot_count_end: number | null
    snapshot_growth: number | null
    expected_snapshots: number | null
    avg_snapshot_retrieval_latency_ms: number | null
    max_snapshot_retrieval_latency_ms: number | null
    avg_trust_report_duration_ms: number | null
    max_trust_report_duration_ms: number | null
    avg_burnin_report_duration_ms: number | null
    max_burnin_report_duration_ms: number | null
    graph_node_count_start: number | null
    graph_node_count_end: number | null
    graph_edge_count_start: number | null
    graph_edge_count_end: number | null
    avg_graph_generation_time_ms: number | null
    max_graph_generation_time_ms: number | null
  }
  samples: BurninSample[]
  sample_count: number
  start_time: string
  end_time: string
  duration_hours: number
}

function fmt(v: number | null | undefined, digits = 1): string {
  if (v == null) return '—'
  return v.toFixed(digits)
}

function pct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function growthArrow(start: number | null, end: number | null): string {
  if (start == null || end == null) return ''
  const delta = end - start
  if (delta > 0) return ` ↑${delta}`
  if (delta < 0) return ` ↓${Math.abs(delta)}`
  return ' →0'
}

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok == null) return <span className={styles.dotUnknown} title="No data">●</span>
  return ok
    ? <span className={styles.dotOk} title="OK">●</span>
    : <span className={styles.dotFail} title="Violation">●</span>
}

interface AreaCardProps {
  title: string
  status?: 'ok' | 'warn' | 'fail' | 'unknown'
  rows: [string, string][]
}

function AreaCard({ title, status = 'unknown', rows }: AreaCardProps) {
  const statusClass = {
    ok: styles.cardOk,
    warn: styles.cardWarn,
    fail: styles.cardFail,
    unknown: styles.cardUnknown,
  }[status]

  return (
    <div className={`${styles.areaCard} ${statusClass}`}>
      <h5 className={styles.areaTitle}>{title}</h5>
      <dl className={styles.areaRows}>
        {rows.map(([label, value]) => (
          <div key={label} className={styles.areaRow}>
            <dt className={styles.areaLabel}>{label}</dt>
            <dd className={styles.areaValue}>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export function BurnInObservations() {
  const { data, loading, error } = useApiFetch<BurninObsReport>(
    '/api/uar/reports/burnin-24h',
    { interval: 60_000 }
  )

  if (loading && !data) {
    return <div className={styles.loading}>Loading burn-in observations…</div>
  }
  if (error) {
    return <div className={styles.error}>Burn-in observations unavailable: {error}</div>
  }
  if (!data?.summary) {
    return <div className={styles.empty}>No burn-in data yet. Start a burn-in run to populate this panel.</div>
  }

  const s = data.summary

  // Derive per-area status
  const cacheStatus: AreaCardProps['status'] =
    s.cache_consistency_violations == null ? 'unknown'
    : s.cache_consistency_violations === 0 ? 'ok'
    : (s.cache_consistency_violation_rate ?? 0) > 0.1 ? 'fail' : 'warn'

  const latestSample = data.samples?.length
    ? data.samples[data.samples.length - 1]
    : null

  const snapshotStatus: AreaCardProps['status'] =
    s.snapshot_count_end == null ? 'unknown'
    : s.expected_snapshots != null && s.snapshot_count_end >= s.expected_snapshots ? 'ok' : 'warn'

  const reportStatus: AreaCardProps['status'] =
    s.avg_trust_report_duration_ms == null ? 'unknown'
    : s.avg_trust_report_duration_ms < 2000 ? 'ok'
    : s.avg_trust_report_duration_ms < 5000 ? 'warn' : 'fail'

  const graphStatus: AreaCardProps['status'] =
    s.avg_graph_generation_time_ms == null ? 'unknown'
    : s.avg_graph_generation_time_ms < 1000 ? 'ok'
    : s.avg_graph_generation_time_ms < 3000 ? 'warn' : 'fail'

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Burn-In Observations</h4>
        <span className={styles.meta}>
          {data.sample_count} samples · {data.duration_hours}h
        </span>
      </div>

      {/* Live cache consistency strip — most recent 20 samples */}
      {data.samples && data.samples.length > 0 && (
        <div className={styles.consistencyStrip}>
          <span className={styles.stripLabel}>Cache consistency (recent)</span>
          <div className={styles.stripDots}>
            {data.samples.slice(-20).map((s, i) => (
              <StatusDot key={`sample-${data.samples.length - 20 + i}`} ok={s.cache_consistency_ok} />
            ))}
          </div>
        </div>
      )}

      <div className={styles.areaGrid}>
        <AreaCard
          title="1 · Cache Consistency"
          status={cacheStatus}
          rows={[
            ['Violations', `${s.cache_consistency_violations ?? '—'}`],
            ['Violation rate', pct(s.cache_consistency_violation_rate)],
            ['Avg delta', fmt(s.avg_cache_consistency_score, 4)],
            ['Max delta', fmt(s.max_cache_consistency_score, 4)],
          ]}
        />

        <AreaCard
          title="2 · Metadata Growth"
          status={s.metadata_key_count_end == null ? 'unknown' : 'ok'}
          rows={[
            ['Keys now', `${s.metadata_key_count_end ?? '—'}${growthArrow(s.metadata_key_count_start, s.metadata_key_count_end)}`],
            ['Avg scan', `${fmt(s.avg_metadata_scan_latency_ms)}ms`],
            ['Max scan', `${fmt(s.max_metadata_scan_latency_ms)}ms`],
          ]}
        />

        <AreaCard
          title="3 · Snapshot Accumulation"
          status={snapshotStatus}
          rows={[
            ['Snapshots', `${s.snapshot_count_end ?? '—'} / ${s.expected_snapshots ?? '—'} expected`],
            ['Growth', `${s.snapshot_growth ?? '—'}`],
            ['Avg retrieval', `${fmt(s.avg_snapshot_retrieval_latency_ms)}ms`],
            ['Max retrieval', `${fmt(s.max_snapshot_retrieval_latency_ms)}ms`],
          ]}
        />

        <AreaCard
          title="4 · Report Timing"
          status={reportStatus}
          rows={[
            ['Trust avg', `${fmt(s.avg_trust_report_duration_ms)}ms`],
            ['Trust max', `${fmt(s.max_trust_report_duration_ms)}ms`],
            ['Burn-in avg', `${fmt(s.avg_burnin_report_duration_ms)}ms`],
            ['Burn-in max', `${fmt(s.max_burnin_report_duration_ms)}ms`],
          ]}
        />

        <AreaCard
          title="5 · Graph Growth"
          status={graphStatus}
          rows={[
            ['Nodes', `${s.graph_node_count_end ?? '—'}${growthArrow(s.graph_node_count_start, s.graph_node_count_end)}`],
            ['Edges', `${s.graph_edge_count_end ?? '—'}${growthArrow(s.graph_edge_count_start, s.graph_edge_count_end)}`],
            ['Avg gen', `${fmt(s.avg_graph_generation_time_ms)}ms`],
            ['Max gen', `${fmt(s.max_graph_generation_time_ms)}ms`],
          ]}
        />

        {latestSample && (
          <AreaCard
            title="Latest Sample"
            status="unknown"
            rows={[
              ['Cache Δ', fmt(latestSample.cache_consistency_score, 4)],
              ['Meta keys', `${latestSample.metadata_key_count ?? '—'}`],
              ['Snapshots', `${latestSample.snapshot_count ?? '—'}`],
              ['Graph', `${latestSample.graph_node_count ?? '—'}N / ${latestSample.graph_edge_count ?? '—'}E`],
            ]}
          />
        )}
      </div>
    </div>
  )
}
