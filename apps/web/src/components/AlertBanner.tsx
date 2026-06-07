import { useState, useCallback } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './AlertBanner.module.css'

interface AlertItem {
  level: 'critical' | 'warning' | 'info'
  source: string
  message: string
  detail?: unknown
  tab?: string
  run_id?: string | null
  signal_id?: string | null
  scope?: string | null
}

interface AlertsSummary {
  hours: number
  count: number
  top_alert: AlertItem
  alerts: AlertItem[]
}

interface FleetSignalData {
  id: string
  level: 'critical' | 'warning' | 'info'
  scope: string
  title: string
  message: string
  latest_run_id: string | null
}

interface MissionControlSnapshot {
  fleet_summary?: {
    top_signal: FleetSignalData | null
  } | null
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

const LEVEL_PRIORITY: Record<string, number> = {
  critical: 0,
  warning: 1,
  info: 2,
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

function _fleetAlertFromMissionControl(mc?: MissionControlSnapshot | null): AlertItem | null {
  const signal = mc?.fleet_summary?.top_signal
  if (!signal || signal.level === 'info') return null
  return {
    level: signal.level,
    source: 'fleet',
    message: `${signal.title}: ${signal.message}`,
    detail: signal,
    tab: 'health',
    run_id: signal.latest_run_id,
    signal_id: signal.id,
    scope: signal.scope,
  }
}

function _pickTopAlert(apiTop: AlertItem | undefined, fleetTop: AlertItem | null): AlertItem | null {
  if (!apiTop) return fleetTop
  if (!fleetTop) return apiTop
  const apiPriority = LEVEL_PRIORITY[apiTop.level] ?? 2
  const fleetPriority = LEVEL_PRIORITY[fleetTop.level] ?? 2
  return fleetPriority < apiPriority ? fleetTop : apiTop
}

interface AlertBannerProps {
  onOpenMissionControl?: (tab?: string) => void
}

export function AlertBanner({ onOpenMissionControl }: AlertBannerProps) {
  const { data, loading, error } = useApiFetch<AlertsSummary>(
    '/api/uar/alerts/summary?hours=24',
    { interval: 30_000 }
  )
  const { data: missionControl } = useApiFetch<MissionControlSnapshot>(
    '/api/uar/mission-control',
    { interval: 30_000 }
  )

  const [manuallyDismissed, setManuallyDismissed] = useState(false)

  const fleetTop = _fleetAlertFromMissionControl(missionControl)
  const top = _pickTopAlert(data?.top_alert, fleetTop)
  const levelClass = top ? LEVEL_CLASS[top.level] || styles.warning : styles.warning
  const alertCount = (data?.alerts.length ?? 0) + (fleetTop ? 1 : 0)

  const handleClick = useCallback(() => {
    if (onOpenMissionControl && top) {
      onOpenMissionControl(top.tab)
    }
  }, [onOpenMissionControl, top])

  const handleDismiss = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      if (top) {
        _dismiss(top)
      }
      setManuallyDismissed(true)
    },
    [top]
  )

  if (loading && !data) return null
  if (error) return null
  if (!top) return null

  // Threshold: only show critical or warning
  if (top.level === 'info') return null

  // Honor persistent dismiss
  if (_isDismissed(top)) return null

  // Honor manual dismiss for this session
  if (manuallyDismissed) return null

  return (
    <div
      className={`${styles.banner} ${levelClass} ${styles.clickable}`}
      role="alert"
      onClick={handleClick}
      title="Click to open Mission Control"
    >
      <span className={styles.icon} aria-hidden="true">
        {LEVEL_ICON[top.level] || '•'}
      </span>
      <span className={styles.message}>{top.message}</span>
      {alertCount > 1 && (
        <span className={styles.count}>+{alertCount - 1}</span>
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
