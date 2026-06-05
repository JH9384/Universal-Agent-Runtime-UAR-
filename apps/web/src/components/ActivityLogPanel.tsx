import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './ActivityLogPanel.module.css'

interface ActivityEvent {
  id: string
  event_type: string
  actor: string
  target: string
  action: string
  details: Record<string, unknown>
  timestamp: number
}

interface ActivityData {
  events: ActivityEvent[]
  count: number
  hours: number
}

interface AlertData {
  metrics: {
    total_fired: number
    acted: number
    ignored: number
    unresolved: number
    action_rate: number
  }
  recent_alerts: {
    id: string
    alert_type: string
    severity: string
    message: string
    fired_at: number
    status: string
  }[]
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

const TYPE_CLASS: Record<string, string> = {
  run: styles.badgeRun,
  skill: styles.badgeSkill,
  outcome: styles.badgeOutcome,
  feedback: styles.badgeFeedback,
  import: styles.badgeImport,
}

export default function ActivityLogPanel() {
  const [hours, setHours] = useState(24)
  const { data, loading, error } = useApiFetch<ActivityData>(
    `/api/uar/activity?hours=${hours}`,
    { interval: 15_000 }
  )
  const { data: alertData } = useApiFetch<AlertData>(
    '/api/uar/alerts',
    { interval: 60_000 }
  )

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading activity...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const events = data?.events ?? []
  const metrics = alertData?.metrics

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Activity Log</h3>
        <div className={styles.actions}>
          <select
            className={styles.select}
            aria-label="Time range"
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          >
            <option value={1}>Last hour</option>
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={72}>Last 3 days</option>
            <option value={168}>Last 7 days</option>
          </select>
          <span className={styles.meta}>{data?.count ?? 0} events</span>
        </div>
      </div>

      {metrics && metrics.total_fired > 0 && (
        <div className={styles.alertBar}>
          <span className={styles.alertLabel}>Alerts</span>
          <span className={styles.alertStat}>
            {metrics.total_fired} fired · {metrics.acted} acted · {metrics.ignored} ignored
          </span>
          {metrics.unresolved > 0 && (
            <span className={styles.alertUnresolved}>{metrics.unresolved} unresolved</span>
          )}
        </div>
      )}

      <div className={styles.list}>
        {events.map((ev) => (
          <div key={ev.id} className={styles.row}>
            <span className={`${styles.typeBadge} ${TYPE_CLASS[ev.event_type] || ''}`}>
              {ev.event_type}
            </span>
            <span className={styles.action}>{ev.action}</span>
            <span className={styles.target} title={ev.target}>{ev.target}</span>
            <span className={styles.actor}>{ev.actor || 'system'}</span>
            <span className={styles.ts}>{formatTs(ev.timestamp)}</span>
          </div>
        ))}
        {events.length === 0 && (
          <div className={styles.empty}>No activity in selected range</div>
        )}
      </div>
    </div>
  )
}
