import { useApiFetch } from '../hooks/useApiFetch'
import styles from './AlertBanner.module.css'

interface AlertItem {
  level: 'critical' | 'warning' | 'info'
  source: string
  message: string
  detail?: unknown
}

interface AlertsSummary {
  hours: number
  count: number
  top_alert: AlertItem
  alerts: AlertItem[]
}

const LEVEL_ICON: Record<string, string> = {
  critical: '🔴',
  warning: '🟡',
  info: '🔵',
}

const LEVEL_CLASS: Record<string, string> = {
  critical: styles.critical,
  warning: styles.warning,
  info: styles.info,
}

export function AlertBanner() {
  const { data, loading, error } = useApiFetch<AlertsSummary>(
    '/api/uar/alerts/summary?hours=24',
    { interval: 30_000 }
  )

  if (loading && !data) return null
  if (error) return null
  if (!data) return null

  const top = data.top_alert
  const levelClass = LEVEL_CLASS[top.level] || styles.info

  return (
    <div className={`${styles.banner} ${levelClass}`}>
      <span className={styles.icon}>{LEVEL_ICON[top.level] || '🔵'}</span>
      <span className={styles.message}>{top.message}</span>
      {data.count > 1 && (
        <span className={styles.count}>+{data.count - 1}</span>
      )}
    </div>
  )
}
