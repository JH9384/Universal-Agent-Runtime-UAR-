import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './FailureClusterPanel.module.css'

interface SkillCluster {
  skill: string
  count: number
  run_count: number
  latest: number
  latest_error?: string
}

interface ErrorCluster {
  error: string
  count: number
  run_count: number
  skill_count: number
  latest: number
}

interface FailureClusterResponse {
  hours: number
  total_runs_scanned: number
  total_failures: number
  top_skills: SkillCluster[]
  top_errors: ErrorCluster[]
}

function MiniBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className={styles.barTrack}>
      <div className={styles.barFill} data-width={Math.round(pct)} />
    </div>
  )
}

export function FailureClusterPanel() {
  const { data, loading, error } = useApiFetch<FailureClusterResponse>(
    '/api/uar/runs/failure-clusters?hours=24&top=10'
  )

  const maxSkillCount = useMemo(() => {
    if (!data?.top_skills?.length) return 1
    return Math.max(...data.top_skills.map((s) => s.count))
  }, [data])

  const maxErrorCount = useMemo(() => {
    if (!data?.top_errors?.length) return 1
    return Math.max(...data.top_errors.map((e) => e.count))
  }, [data])

  if (loading) return <div className={styles.loading}>Loading failure clusters…</div>
  if (error) return <div className={styles.error}>Clusters failed: {error}</div>

  return (
    <div className={styles.clusterPanel}>
      <h4 className={styles.panelTitle}>Failure Clusters</h4>
      <p className={styles.panelDesc}>
        {data?.total_failures ?? 0} failures across {data?.total_runs_scanned ?? 0} runs
        (last {data?.hours ?? 24}h)
      </p>

      {/* Top failing skills */}
      {data && data.top_skills.length > 0 && (
        <div className={styles.clusterSection}>
          <h5 className={styles.sectionTitle}>Top Failing Skills</h5>
          <div className={styles.clusterList}>
            {data.top_skills.map((sc) => (
              <div key={sc.skill} className={styles.clusterRow}>
                <div className={styles.clusterMeta}>
                  <span className={styles.clusterName}>{sc.skill}</span>
                  <span className={styles.clusterCount}>{sc.count} failures</span>
                  <span className={styles.clusterRuns}>{sc.run_count} runs</span>
                </div>
                <MiniBar value={sc.count} max={maxSkillCount} />
                {sc.latest_error && (
                  <span className={styles.clusterLatest}>{sc.latest_error}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top error messages */}
      {data && data.top_errors.length > 0 && (
        <div className={styles.clusterSection}>
          <h5 className={styles.sectionTitle}>Top Error Patterns</h5>
          <div className={styles.clusterList}>
            {data.top_errors.map((ec) => (
              <div key={ec.error} className={styles.clusterRow}>
                <div className={styles.clusterMeta}>
                  <span className={styles.clusterName} title={ec.error}>
                    {ec.error.length > 60 ? ec.error.slice(0, 60) + '…' : ec.error}
                  </span>
                  <span className={styles.clusterCount}>{ec.count}×</span>
                  <span className={styles.clusterRuns}>{ec.run_count} runs</span>
                  <span className={styles.clusterRuns}>{ec.skill_count} skills</span>
                </div>
                <MiniBar value={ec.count} max={maxErrorCount} />
              </div>
            ))}
          </div>
        </div>
      )}

      {data && data.top_skills.length === 0 && data.top_errors.length === 0 && (
        <div className={styles.emptyState}>
          No failures detected in the last {data.hours}h. The system is clean.
        </div>
      )}
    </div>
  )
}
