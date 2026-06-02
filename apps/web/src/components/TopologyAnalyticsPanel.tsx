import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './TopologyAnalyticsPanel.module.css'

interface HotNode {
  skill: string
  invocations: number
  success_rate: number
}

interface HotEdge {
  source: string
  target: string
  transitions: number
  success_rate: number
}

interface RecipeUtil {
  recipe: string
  executions: number
  success_rate: number
}

interface HotPathsResponse {
  hours: number
  total_runs: number
  nodes: HotNode[]
  edges: HotEdge[]
  recipes: RecipeUtil[]
}

function RateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  return (
    <div className={styles.rateTrack}>
      <div
        className={styles.rateFill}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function SuccessPill({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color =
    pct >= 90 ? styles.pillGreen : pct >= 70 ? styles.pillYellow : styles.pillRed
  return <span className={`${styles.pill} ${color}`}>{pct}%</span>
}

export function TopologyAnalyticsPanel() {
  const { data, loading, error } = useApiFetch<HotPathsResponse>(
    '/api/uar/topology/hot-paths?hours=168&top=10'
  )

  const maxInvocations = useMemo(() => {
    if (!data?.nodes?.length) return 1
    return Math.max(...data.nodes.map((n) => n.invocations))
  }, [data])

  const maxTransitions = useMemo(() => {
    if (!data?.edges?.length) return 1
    return Math.max(...data.edges.map((e) => e.transitions))
  }, [data])

  if (loading) return <div className={styles.loading}>Loading topology analytics…</div>
  if (error) return <div className={styles.error}>Analytics failed: {error}</div>

  return (
    <div className={styles.analyticsPanel}>
      <h4 className={styles.panelTitle}>Topology Hot Paths</h4>
      <p className={styles.panelDesc}>
        {data?.total_runs ?? 0} runs analyzed · {data?.hours ?? 168}h window
      </p>

      {/* Hot Nodes */}
      {data && data.nodes.length > 0 && (
        <div className={styles.section}>
          <h5 className={styles.sectionTitle}>Most Used Skills</h5>
          <div className={styles.table}>
            <div className={styles.tableHeader}>
              <span>Skill</span>
              <span>Invocations</span>
              <span>Success</span>
            </div>
            {data.nodes.map((n) => (
              <div key={n.skill} className={styles.tableRow}>
                <span className={styles.cellName}>{n.skill}</span>
                <span className={styles.cellCount}>{n.invocations}</span>
                <SuccessPill rate={n.success_rate} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hot Edges */}
      {data && data.edges.length > 0 && (
        <div className={styles.section}>
          <h5 className={styles.sectionTitle}>Hot Transitions</h5>
          <div className={styles.edgeList}>
            {data.edges.map((e) => (
              <div key={`${e.source}→${e.target}`} className={styles.edgeRow}>
                <div className={styles.edgePath}>
                  <span className={styles.edgeNode}>{e.source}</span>
                  <span className={styles.edgeArrow}>→</span>
                  <span className={styles.edgeNode}>{e.target}</span>
                </div>
                <div className={styles.edgeMeta}>
                  <span className={styles.edgeCount}>{e.transitions}×</span>
                  <SuccessPill rate={e.success_rate} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recipe Utilization */}
      {data && data.recipes.length > 0 && (
        <div className={styles.section}>
          <h5 className={styles.sectionTitle}>Recipe Utilization</h5>
          <div className={styles.table}>
            <div className={styles.tableHeader}>
              <span>Recipe</span>
              <span>Runs</span>
              <span>Success</span>
            </div>
            {data.recipes.map((r) => (
              <div key={r.recipe} className={styles.tableRow}>
                <span className={styles.cellName}>{r.recipe}</span>
                <span className={styles.cellCount}>{r.executions}</span>
                <SuccessPill rate={r.success_rate} />
              </div>
            ))}
          </div>
        </div>
      )}

      {data &&
        data.nodes.length === 0 &&
        data.edges.length === 0 &&
        data.recipes.length === 0 && (
          <div className={styles.emptyState}>
            No execution data in the last {data.hours}h. Run some goals to
            build topology analytics.
          </div>
        )}
    </div>
  )
}
