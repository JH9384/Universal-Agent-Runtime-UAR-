import { useApiFetch } from '../hooks/useApiFetch'
import styles from './MorningBriefing.module.css'

interface BriefingData {
  greeting: string
  generated_at: number
  drift_events: number
  trust_drops: number
  trust_stable: boolean
  open_incidents: number
  unresolved_recommendations: number
  top_trusted_type: string | null
  top_trust_score: number | null
  summary_text: string
}

export function MorningBriefing() {
  const { data, loading, error } = useApiFetch<BriefingData>(
    '/api/uar/briefing',
    { interval: 60_000 }
  )

  if (loading && !data) {
    return (
      <div className={styles.briefing}>
        <div className={styles.loading}>Loading briefing…</div>
      </div>
    )
  }
  if (error) {
    return (
      <div className={styles.briefing}>
        <div className={styles.error}>Briefing unavailable: {error}</div>
      </div>
    )
  }
  if (!data) return null

  const hasAttention =
    data.drift_events > 0 ||
    data.trust_drops > 0 ||
    data.open_incidents > 0

  return (
    <div className={`${styles.briefing} ${hasAttention ? styles.attention : ''}`}>
      <div className={styles.header}>
        <h3 className={styles.title}>{data.greeting}</h3>
        <span className={styles.timestamp}>
          {new Date(data.generated_at * 1000).toLocaleTimeString()}
        </span>
      </div>

      <p className={styles.narrative}>{data.summary_text}</p>

      <div className={styles.statsRow}>
        <StatPill
          label="Drift"
          value={data.drift_events}
          alert={data.drift_events > 0}
        />
        <StatPill
          label="Trust Drops"
          value={data.trust_drops}
          alert={data.trust_drops > 0}
        />
        <StatPill
          label="Open Incidents"
          value={data.open_incidents}
          alert={data.open_incidents > 0}
        />
        <StatPill
          label="Unresolved"
          value={data.unresolved_recommendations}
          alert={data.unresolved_recommendations > 5}
        />
      </div>

      {data.top_trusted_type && (
        <div className={styles.topTrusted}>
          Top trusted:{' '}
          <strong>{data.top_trusted_type}</strong>
          {' '}({data.top_trust_score?.toFixed(2)})
        </div>
      )}
    </div>
  )
}

function StatPill({
  label,
  value,
  alert,
}: {
  label: string
  value: number
  alert: boolean
}) {
  return (
    <div className={`${styles.pill} ${alert ? styles.pillAlert : ''}`}>
      <span className={styles.pillValue}>{value}</span>
      <span className={styles.pillLabel}>{label}</span>
    </div>
  )
}
