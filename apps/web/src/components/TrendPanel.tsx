import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './TrendPanel.module.css'

interface Snapshot {
  timestamp: number
  runtime_health?: { score?: number; tier?: string } | null
  replay_confidence?: { score?: number; tier?: string } | null
  certification?: { score?: number; level?: string } | null
}

interface HistoryResponse {
  hours: number
  count: number
  snapshots: Snapshot[]
}

function Sparkline({
  data,
  width = 240,
  height = 60,
  color = '#2980b9',
}: {
  data: number[]
  width?: number
  height?: number
  color?: string
}) {
  if (data.length < 2) {
    return (
      <div className={styles.sparklinePlaceholder}>
        <span className={styles.muted}>Not enough data</span>
      </div>
    )
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * (height - 4) - 2
    return [x, y]
  })

  const pathD = points.reduce((d, [x, y], i) => {
    return d + (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`)
  }, '')

  const areaD =
    pathD +
    ` L ${points[points.length - 1][0]} ${height}` +
    ` L ${points[0][0]} ${height} Z`

  return (
    <svg width={width} height={height} className={styles.sparkline}>
      <path d={areaD} fill={color} opacity={0.08} />
      <path d={pathD} fill="none" stroke={color} strokeWidth={2} />
      {/* Current value dot */}
      <circle
        cx={points[points.length - 1][0]}
        cy={points[points.length - 1][1]}
        r={3}
        fill={color}
      />
    </svg>
  )
}

function TrendCard({
  label,
  current,
  min,
  max,
  data,
  color,
}: {
  label: string
  current: number
  min: number
  max: number
  data: number[]
  color: string
}) {
  return (
    <div className={styles.trendCard}>
      <div className={styles.trendHeader}>
        <span className={styles.trendLabel}>{label}</span>
        <span className={styles.trendCurrent}>
          {current}
        </span>
      </div>
      <Sparkline data={data} color={color} />
      <div className={styles.trendFooter}>
        <span className={styles.trendStat}>Min: {min}</span>
        <span className={styles.trendStat}>Max: {max}</span>
      </div>
    </div>
  )
}

export function TrendPanel() {
  const { data, loading, error } = useApiFetch<HistoryResponse>(
    '/api/uar/mission-control/history?hours=24'
  )

  const snapshots = useMemo(() => data?.snapshots || [], [data])

  const healthSeries = useMemo(
    () =>
      snapshots
        .map((s) => s.runtime_health?.score)
        .filter((v): v is number => typeof v === 'number'),
    [snapshots]
  )

  const confidenceSeries = useMemo(
    () =>
      snapshots
        .map((s) => s.replay_confidence?.score)
        .filter((v): v is number => typeof v === 'number'),
    [snapshots]
  )

  const certSeries = useMemo(
    () =>
      snapshots
        .map((s) => s.certification?.score)
        .filter((v): v is number => typeof v === 'number'),
    [snapshots]
  )

  if (loading) return <div className={styles.loading}>Loading trends…</div>
  if (error) return <div className={styles.error}>Trends failed: {error}</div>

  return (
    <div className={styles.trendPanel}>
      <h4 className={styles.panelTitle}>Trends (24h)</h4>
      <p className={styles.panelDesc}>
        {snapshots.length} snapshot{snapshots.length !== 1 ? 's' : ''} recorded
      </p>

      <div className={styles.trendGrid}>
        {healthSeries.length >= 2 && (
          <TrendCard
            label="Runtime Health"
            current={healthSeries[healthSeries.length - 1]}
            min={Math.min(...healthSeries)}
            max={Math.max(...healthSeries)}
            data={healthSeries}
            color="#2980b9"
          />
        )}

        {confidenceSeries.length >= 2 && (
          <TrendCard
            label="Replay Confidence"
            current={confidenceSeries[confidenceSeries.length - 1]}
            min={Math.min(...confidenceSeries)}
            max={Math.max(...confidenceSeries)}
            data={confidenceSeries}
            color="#27ae60"
          />
        )}

        {certSeries.length >= 2 && (
          <TrendCard
            label="Certification"
            current={certSeries[certSeries.length - 1]}
            min={Math.min(...certSeries)}
            max={Math.max(...certSeries)}
            data={certSeries}
            color="#f39c12"
          />
        )}
      </div>

      {healthSeries.length < 2 &&
        confidenceSeries.length < 2 &&
        certSeries.length < 2 && (
          <div className={styles.emptyState}>
            Not enough historical data yet. Trends appear after multiple
            Mission Control snapshots are collected.
          </div>
        )}
    </div>
  )
}
