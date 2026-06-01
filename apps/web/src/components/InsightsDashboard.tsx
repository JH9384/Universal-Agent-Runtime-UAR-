import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './InsightsDashboard.module.css'

type InsightTab = 'patterns' | 'evolution' | 'workflows' | 'clusters' | 'operator'

const TABS: { key: InsightTab; label: string }[] = [
  { key: 'patterns', label: 'Patterns' },
  { key: 'evolution', label: 'Evolution' },
  { key: 'workflows', label: 'Workflows' },
  { key: 'clusters', label: 'Clusters' },
  { key: 'operator', label: 'Intelligence' },
]

export function InsightsDashboard() {
  const [tab, setTab] = useState<InsightTab>('patterns')
  const { data, loading, error } = useApiFetch<any>(`/api/uar/insights/${tab}`)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Insight Generation</h4>
        <div className={styles.tabs}>
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className={styles.loading}>Generating insights…</div>}
      {error && <div className={styles.error}>{error}</div>}

      {data && (
        <div className={styles.reportBody}>
          <div className={styles.narrative}>{data.narrative}</div>

          {tab === 'patterns' && <PatternsView data={data} />}
          {tab === 'evolution' && <EvolutionView data={data} />}
          {tab === 'workflows' && <WorkflowsView data={data} />}
          {tab === 'clusters' && <ClustersView data={data} />}
          {tab === 'operator' && <OperatorView data={data} />}
        </div>
      )}
    </div>
  )
}

function PatternsView({ data }: { data: any }) {
  return (
    <>
      <div className={styles.statGrid}>
        <StatBox label="Total" value={data.total_incidents} />
        <StatBox label="Avg Resolution (h)" value={data.avg_resolution_seconds ? (data.avg_resolution_seconds / 3600).toFixed(1) : '—'} />
      </div>
      {data.recurring_themes?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Recurring Themes</h5>
          {data.recurring_themes.map((t: any) => (
            <div key={t.word} className={styles.themeRow}>
              <span>{t.word}</span>
              <span className={styles.themeCount}>{t.count}</span>
            </div>
          ))}
        </>
      )}
      {data.hot_runs?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Hot Runs</h5>
          {data.hot_runs.map((r: any) => (
            <div key={r.run_id} className={styles.hotRunRow}>
              <span className={styles.hotRunId}>{r.run_id}</span>
              <span>{r.incident_count} incidents</span>
            </div>
          ))}
        </>
      )}
      {Object.keys(data.severity_distribution || {}).length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Severity</h5>
          {Object.entries(data.severity_distribution).map(([k, v]: [string, any]) => (
            <DistRow key={k} band={k} count={v} />
          ))}
        </>
      )}
    </>
  )
}

function EvolutionView({ data }: { data: any }) {
  return (
    <>
      <div className={styles.statGrid}>
        <StatBox label="Snapshots" value={data.snapshot_count} />
        <StatBox label="Types" value={Object.keys(data.trajectories || {}).length} />
      </div>
      {data.velocities?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Trust Velocity</h5>
          {data.velocities.map((v: any) => (
            <div key={v.type} className={`${styles.velocityRow} ${styles[v.direction] || ''}`}>
              <span className={styles.velType}>{v.type}</span>
              <span className={styles.velDelta}>{v.delta > 0 ? '+' : ''}{v.delta}</span>
              <span className={`${styles.velBadge} ${styles[`badge${v.direction}`] || ''}`}>{v.direction}</span>
            </div>
          ))}
        </>
      )}
    </>
  )
}

function WorkflowsView({ data }: { data: any }) {
  return (
    <>
      <div className={styles.statGrid}>
        <StatBox label="Total" value={data.total_investigations} />
        <StatBox label="Resolved" value={data.resolved_count} />
        <StatBox label="Rate" value={`${Math.round((data.resolution_rate || 0) * 100)}%`} />
      </div>
      {data.common_sequences?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Common Resolution Paths</h5>
          {data.common_sequences.map((s: any, i: number) => (
            <div key={i} className={styles.sequenceRow}>
              <span className={styles.seqText}>{s.sequence}</span>
              <span className={styles.seqCount}>{s.count}x</span>
            </div>
          ))}
        </>
      )}
      {data.top_actions?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Top Actions</h5>
          {data.top_actions.map((a: any) => (
            <div key={a.type} className={styles.actionRow}>
              <span>{a.type}</span>
              <span className={styles.actionCount}>{a.count}</span>
            </div>
          ))}
        </>
      )}
    </>
  )
}

function ClustersView({ data }: { data: any }) {
  return (
    <>
      {data.incident_clusters?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Incident Clusters</h5>
          {data.incident_clusters.map((c: any, i: number) => (
            <div key={i} className={styles.clusterRow}>
              <span className={styles.clusterId}>{c.incident_a}</span>
              <span>↔</span>
              <span className={styles.clusterId}>{c.incident_b}</span>
              <span className={styles.clusterShared}>{c.shared_runs} runs</span>
            </div>
          ))}
        </>
      )}
      {Object.keys(data.recommendation_category_counts || {}).length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Recommendation Categories</h5>
          {Object.entries(data.recommendation_category_counts).map(([k, v]: [string, any]) => (
            <DistRow key={k} band={k} count={v} />
          ))}
        </>
      )}
    </>
  )
}

function OperatorView({ data }: { data: any }) {
  return (
    <>
      <div className={styles.statGrid}>
        <StatBox label="Resolved" value={data.total_resolved} />
        <StatBox label="Unresolved" value={data.total_unresolved} />
      </div>
      {data.action_lift?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Action Lift (Resolved vs Unresolved)</h5>
          {data.action_lift.map((a: any) => (
            <div key={a.action} className={styles.liftRow}>
              <span>{a.action}</span>
              <span className={styles.liftValue}>lift {a.lift}x</span>
              <span className={styles.liftDetail}>{a.resolved_count}R / {a.unresolved_count}U</span>
            </div>
          ))}
        </>
      )}
      {data.fastest_resolution_paths?.length > 0 && (
        <>
          <h5 className={styles.sectionTitle}>Fastest Resolution Starts</h5>
          {data.fastest_resolution_paths.map((p: any) => (
            <div key={p.first_action} className={styles.fastRow}>
              <span>{p.first_action}</span>
              <span className={styles.fastTime}>{(p.avg_seconds / 60).toFixed(0)} min avg</span>
              <span className={styles.fastCount}>{p.count}x</span>
            </div>
          ))}
        </>
      )}
    </>
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
