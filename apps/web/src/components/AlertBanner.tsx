import { useState, useCallback } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './AlertBanner.module.css'

interface AlertItem {
  level: 'critical' | 'warning' | 'info'
  source: string
  message: string
  detail?: unknown
  tab?: string
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

const DISMISS_PREFIX = 'uar_alert_dismissed_'
const DISMISS_TTL_MS = 24 * 60 * 60 * 1000 // 24 hours

function _dismissKey(alert: AlertItem): string {
  return `${DISMISS_PREFIX}${alert.source}:${alert.message}`
}

function _isDismissed(alert: AlertItem): boolean {
  try {
    const raw = localStorage.getItem(_dismissKey(alert))
    if (!raw) return false
    const parsed = JSON.parse(raw)
    if (typeof parsed.ts === 'number') {
      return Date.now() - parsed.ts < DISMISS_TTL_MS
    }
    // Legacy plain '1' values: treat as expired (migrate to TTL)
    return false
  } catch {
    return false
  }
}

function _dismiss(alert: AlertItem): void {
  try {
    localStorage.setItem(_dismissKey(alert), JSON.stringify({ ts: Date.now() }))
  } catch {
    /* noop */
  }
}

interface AlertBannerProps {
  onOpenMissionControl?: (tab?: string) => void
}

export function AlertBanner({ onOpenMissionControl }: AlertBannerProps) {
  const { data, loading, error } = useApiFetch<AlertsSummary>(
    '/api/uar/alerts/summary?hours=24',
    { interval: 30_000 }
  )

  const [manuallyDismissed, setManuallyDismissed] = useState(false)

  if (loading && !data) return null
  if (error) return null
  if (!data || !data.top_alert) return null

  const top = data.top_alert

  // Threshold: only show critical or warning
  if (top.level === 'info') return null

  // Honor persistent dismiss
  if (_isDismissed(top)) return null

  // Honor manual dismiss for this session
  if (manuallyDismissed) return null

  const levelClass = LEVEL_CLASS[top.level] || styles.warning

  const handleClick = useCallback(() => {
    if (onOpenMissionControl) {
      onOpenMissionControl(top.tab)
    }
  }, [onOpenMissionControl, top.tab])

  const handleDismiss = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      _dismiss(top)
      setManuallyDismissed(true)
    },
    [top]
  )

  return (
    <div
      className={`${styles.banner} ${levelClass} ${styles.clickable}`}
      role="alert"
      onClick={handleClick}
      title="Click to open Mission Control"
    >
      <span className={styles.icon} aria-hidden="true">
        {LEVEL_ICON[top.level] || '�'}
      </span>
      <span className={styles.message}>{top.message}</span>
      {data.alerts.length > 1 && (
        <span className={styles.count}>+{data.alerts.length - 1}</span>
      )}
      <button
        className={styles.dismissBtn}
        onClick={handleDismiss}
        title="Dismiss"
        aria-label="Dismiss alert"
      >
        ×
      </button>
    </div>
  )
}
