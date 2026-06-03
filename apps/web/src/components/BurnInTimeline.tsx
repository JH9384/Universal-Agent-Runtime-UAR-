import { useApiFetch } from '../hooks/useApiFetch'
import styles from './BurnInTimeline.module.css'

interface TrustTypeData {
  type: string
  trust_score: number
  drift_penalty: number
}

interface TrustResponse {
  generated_at: number
  system_calibration_error: number
  recommendation_types: TrustTypeData[]
}

interface RecommendationItem {
  recommendation_id: string
  title: string
  category: string
  confidence: number
  trust_score: number
  adaptive_modifier: number
  drift_penalty: number
}

interface RecommendationsResponse {
  generated_at: number
  recommendations: RecommendationItem[]
  trust: TrustResponse | null
}

type EventType = 'validation' | 'drift' | 'calibration' | 'divergence'

interface TimelineEvent {
  id: string
  type: EventType
  label: string
  detail: string
  severity: 'info' | 'warning' | 'alert'
  timestamp: string
}

function buildTimeline(
  recs: RecommendationsResponse | null,
  trust: TrustResponse | null,
): TimelineEvent[] {
  const events: TimelineEvent[] = []

  if (!recs && !trust) return events

  // Validation event — current trust snapshot
  if (trust) {
    const driftTypes = trust.recommendation_types.filter(
      (t) => t.drift_penalty > 0
    )
    if (driftTypes.length > 0) {
      events.push({
        id: `drift-${trust.generated_at}`,
        type: 'drift',
        label: `${driftTypes.length} drift signal(s)`,
        detail: driftTypes.map((t) => `${t.type} (-${t.drift_penalty})`).join(', '),
        severity: 'warning',
        timestamp: new Date(trust.generated_at * 1000).toLocaleString(),
      })
    }

    events.push({
      id: `cal-${trust.generated_at}`,
      type: 'calibration',
      label: `Calibration: ${trust.system_calibration_error?.toFixed(3) ?? '—'}`,
      detail: `${trust.recommendation_types.length} recommendation type(s) tracked`,
      severity: 'info',
      timestamp: new Date(trust.generated_at * 1000).toLocaleString(),
    })
  }

  // Divergence events from current recommendations
  if (recs?.recommendations) {
    const divergences = recs.recommendations.filter(
      (r) =>
        (r.confidence > 0.90 && (r.trust_score ?? 0) < 0.40) ||
        (r.confidence < 0.50 && (r.trust_score ?? 0) > 0.80)
    )
    if (divergences.length > 0) {
      events.push({
        id: `div-${recs.generated_at}`,
        type: 'divergence',
        label: `${divergences.length} divergence case(s)`,
        detail: divergences.map((d) => d.title).join(' · '),
        severity: 'alert',
        timestamp: new Date(recs.generated_at * 1000).toLocaleString(),
      })
    }
  }

  return events
}

function eventIcon(type: EventType): string {
  if (type === 'drift') return '🌊'
  if (type === 'calibration') return '⚖️'
  if (type === 'divergence') return '⚠️'
  return '📋'
}

function severityClass(severity: string): string {
  if (severity === 'alert') return styles.severityAlert
  if (severity === 'warning') return styles.severityWarning
  return styles.severityInfo
}

export function BurnInTimeline() {
  const { data: recsData, loading: recsLoading } =
    useApiFetch<RecommendationsResponse>(
      '/api/uar/recommendations?hours=24&limit=100',
      { interval: 30_000 }
    )

  const { data: trustData, loading: trustLoading } =
    useApiFetch<TrustResponse>(
      '/api/uar/recommendations/trust',
      { interval: 30_000 }
    )

  const loading = recsLoading || trustLoading

  const events = buildTimeline(recsData ?? null, trustData ?? null)

  if (loading) return <div className={styles.loading}>Loading timeline…</div>

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h4 className={styles.panelTitle}>Burn-In Timeline</h4>
        <span className={styles.meta}>{events.length} event(s)</span>
      </div>

      {events.length === 0 ? (
        <div className={styles.emptyState}>No validation events yet.</div>
      ) : (
        <div className={styles.timeline}>
          {events.map((ev) => (
            <div key={ev.id} className={`${styles.timelineItem} ${severityClass(ev.severity)}`}>
              <div className={styles.timelineIcon}>{eventIcon(ev.type)}</div>
              <div className={styles.timelineContent}>
                <div className={styles.timelineLabel}>{ev.label}</div>
                <div className={styles.timelineDetail}>{ev.detail}</div>
                <div className={styles.timelineTimestamp}>{ev.timestamp}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
