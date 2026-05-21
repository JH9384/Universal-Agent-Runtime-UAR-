import { useMemo } from 'react'
import styles from './MetricsDashboard.module.css'

interface SkillTime {
  skill: string
  time_ms: number
}

interface MetricsPayload {
  total_time_sec?: number
  event_count?: number
  cache_hits?: number
  cache_misses?: number
  recipe_cache_hits?: number
  recipe_cache_misses?: number
  skills_executed?: number
  skill_times_ms?: Record<string, number>
}

interface MetricsDashboardProps {
  metrics: MetricsPayload | null
  darkMode?: boolean
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toFixed(0)}s`
}

export function MetricsDashboard({ metrics, darkMode = false }: MetricsDashboardProps) {
  const skillTimes = useMemo(() => {
    if (!metrics?.skill_times_ms) return []
    return Object.entries(metrics.skill_times_ms)
      .map(([skill, time_ms]) => ({ skill, time_ms }))
      .sort((a, b) => b.time_ms - a.time_ms)
  }, [metrics])

  const cacheStats = useMemo(() => {
    if (!metrics) return null
    const hits = metrics.cache_hits ?? 0
    const misses = metrics.cache_misses ?? 0
    const total = hits + misses
    const rate = total > 0 ? (hits / total) * 100 : 0
    return { hits, misses, total, rate }
  }, [metrics])

  const recipeCacheStats = useMemo(() => {
    if (!metrics) return null
    const rh = metrics.recipe_cache_hits ?? 0
    const rm = metrics.recipe_cache_misses ?? 0
    const rt = rh + rm
    return { hits: rh, misses: rm, total: rt, rate: rt > 0 ? (rh / rt) * 100 : 0 }
  }, [metrics])

  if (!metrics) {
    return (
      <div className={`${styles.empty} ${darkMode ? styles.dark : ''}`}>
        <span className={styles.emptyIcon}>📊</span>
        <p>Run a workflow to see metrics.</p>
      </div>
    )
  }

  const maxSkillTime = skillTimes.length > 0 ? skillTimes[0].time_ms : 1
  const barMaxWidth = 200

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      {/* Summary cards */}
      <div className={styles.summaryGrid}>
        <div className={styles.card}>
          <div className={styles.cardLabel}>Total Time</div>
          <div className={styles.cardValue}>
            {formatDuration(metrics.total_time_sec ?? 0)}
          </div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>Events</div>
          <div className={styles.cardValue}>{metrics.event_count ?? 0}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>Skills Executed</div>
          <div className={styles.cardValue}>{metrics.skills_executed ?? 0}</div>
        </div>
      </div>

      {/* Cache stats */}
      {cacheStats && cacheStats.total > 0 && (
        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>Skill Cache Performance</h4>
          <div className={styles.cacheRow}>
            <div className={styles.cacheBarBg}>
              <div
                className={styles.cacheBarHit}
                style={{ width: `${cacheStats.rate}%` }}
              />
            </div>
            <div className={styles.cacheLegend}>
              <span className={styles.cacheHit}>● {cacheStats.hits} hits</span>
              <span className={styles.cacheMiss}>● {cacheStats.misses} misses</span>
              <span className={styles.cacheRate}>{cacheStats.rate.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      {recipeCacheStats && recipeCacheStats.total > 0 && (
        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>Recipe Cache Performance</h4>
          <div className={styles.cacheRow}>
            <div className={styles.cacheBarBg}>
              <div
                className={styles.cacheBarHit}
                style={{ width: `${recipeCacheStats.rate}%` }}
              />
            </div>
            <div className={styles.cacheLegend}>
              <span className={styles.cacheHit}>● {recipeCacheStats.hits} hits</span>
              <span className={styles.cacheMiss}>● {recipeCacheStats.misses} misses</span>
              <span className={styles.cacheRate}>{recipeCacheStats.rate.toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Skill times bar chart */}
      {skillTimes.length > 0 && (
        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>Skill Execution Times</h4>
          <div className={styles.chart}>
            {skillTimes.map(({ skill, time_ms }) => {
              const width = (time_ms / maxSkillTime) * barMaxWidth
              return (
                <div key={skill} className={styles.barRow}>
                  <span className={styles.barLabel} title={skill}>
                    {skill}
                  </span>
                  <div className={styles.barTrack}>
                    <div
                      className={styles.barFill}
                      style={{ width: `${Math.max(width, 2)}px` }}
                    />
                  </div>
                  <span className={styles.barValue}>
                    {time_ms >= 1000
                      ? `${(time_ms / 1000).toFixed(1)}s`
                      : `${time_ms.toFixed(0)}ms`}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
