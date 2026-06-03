import { useApiFetch } from '../hooks/useApiFetch'
import { logAuditEvent } from '../utils/analyticsInstrumentation'
import styles from './FailureHotspotPanel.module.css'

interface HotspotNode {
  skill: string
  invocations: number
  failures: number
  failure_rate: number
  severity: string
  affected_runs: number
  run_ids: string[]
}

interface HotspotEdge {
  source: string
  target: string
  transitions: number
  failures: number
  failure_rate: number
  severity: string
  affected_runs: number
  run_ids: string[]
}

interface HotspotResponse {
  hours: number
  total_runs: number
  total_failures: number
  nodes: HotspotNode[]
  edges: HotspotEdge[]
}

function severityClass(sev: string): string {
  const s = sev.toLowerCase()
  if (s === 'critical') return styles.sevCritical
  if (s === 'warning') return styles.sevWarning
  return styles.sevHealthy
}

function severityLabel(sev: string): string {
  const s = sev.toLowerCase()
  if (s === 'critical') return '🔴 Critical'
  if (s === 'warning') return '🟡 Warning'
  return '🟢 Healthy'
}

function Bar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  return (
    <div className={styles.barTrack}>
      <div className={styles.barFill} style={{ width: `${pct}%` }} />
    </div>
  )
}

interface FailureHotspotPanelProps {
  onOpenReplay?: (runId: string) => void
}

function ReplayButton({ runIds, onOpen, panel }: { runIds: string[]; onOpen?: (runId: string) => void; panel: string }) {
  if (!onOpen || runIds.length === 0) return null
  return (
    <button
      className={styles.replayBtn}
      onClick={() => {
        logAuditEvent(panel, runIds[0], 'replay_clicked')
        onOpen(runIds[0])
      }}
      title={`Replay ${runIds.length} run(s)`}
    >
      ▶ Replay
    </button>
  )
}

export function FailureHotspotPanel({ onOpenReplay }: FailureHotspotPanelProps) {
  const { data, loading, error } = useApiFetch<HotspotResponse>(
    '/api/uar/topology/failure-hotspots?hours=168&top=10',
    { interval: 30_000 }
  )

  if (loading) return <div className={styles.loading}>Loading hotspots…</div>
  if (error) return <div className={styles.error}>Hotspots failed: {error}</div>

  return (
    <div className={styles.hotspotPanel}>
      <h4 className={styles.panelTitle}>Failure Hotspots</h4>
      <p className={styles.panelDesc}>
        {data?.total_failures ?? 0} failures across {data?.total_runs ?? 0} runs
        (last {data?.hours ?? 168}h)
      </p>

      {/* Nodes */}
      {data && data.nodes.length > 0 && (
        <div className={styles.section}>
          <h5 className={styles.sectionTitle}>Most Dangerous Skills</h5>
          <div className={styles.table}>
            <div className={styles.tableHeader}>
              <span>Skill</span>
              <span>Rate</span>
              <span>Runs</span>
              <span>Severity</span>
            </div>
            {data.nodes.map((n) => (
              <div key={n.skill} className={styles.tableRow}>
                <span className={styles.cellName}>{n.skill}</span>
                <span className={styles.cellRate}>
                  {Math.round(n.failure_rate * 100)}%
                  <Bar rate={n.failure_rate} />
                </span>
                <span className={styles.cellCount}>{n.affected_runs}</span>
                <span className={`${styles.severityBadge} ${severityClass(n.severity)}`}>
                  {severityLabel(n.severity)}
                </span>
                <ReplayButton runIds={n.run_ids || []} onOpen={onOpenReplay} panel="failure_hotspot" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edges */}
      {data && data.edges.length > 0 && (
        <div className={styles.section}>
          <h5 className={styles.sectionTitle}>Most Dangerous Transitions</h5>
          <div className={styles.edgeList}>
            {data.edges.map((e) => (
              <div key={`${e.source}→${e.target}`} className={styles.edgeRow}>
                <div className={styles.edgePath}>
                  <span className={styles.edgeNode}>{e.source}</span>
                  <span className={styles.edgeArrow}>→</span>
                  <span className={styles.edgeNode}>{e.target}</span>
                </div>
                <div className={styles.edgeMeta}>
                  <span className={styles.edgeRate}>
                    {Math.round(e.failure_rate * 100)}%
                  </span>
                  <Bar rate={e.failure_rate} />
                  <span className={styles.edgeRuns}>{e.affected_runs} runs</span>
                </div>
                <span className={`${styles.severityBadge} ${severityClass(e.severity)}`}>
                  {severityLabel(e.severity)}
                </span>
                <ReplayButton runIds={e.run_ids || []} onOpen={onOpenReplay} panel="failure_hotspot" />
              </div>
            ))}
          </div>
        </div>
      )}

      {data &&
        data.nodes.length === 0 &&
        data.edges.length === 0 && (
          <div className={styles.emptyState}>
            No failure hotspots detected. All skills and transitions are
            healthy in the last {data.hours}h.
          </div>
        )}
    </div>
  )
}
