import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './RecommendationPanel.module.css'

interface Recommendation {
  recommendation_id: string
  category: string
  priority: string
  confidence: number
  base_confidence: number
  adaptive_modifier: number
  trust_score: number
  title: string
  description: string
  source: string
  affected_runs: string[]
}

interface TrustData {
  generated_at: number | null
  system_calibration_error: number | null
  recommendation_types: { type: string; trust_score: number }[]
}

interface RecommendationsResponse {
  generated_at: number
  hours: number
  runs_analyzed: number
  trust_ranking_enabled: boolean
  recommendations: Recommendation[]
  trust: TrustData | null
  sources: {
    recurring_patterns: number
    recovery_paths: number
    topology_points: number
    governance_periods: number
  }
}

function priorityClass(priority: string): string {
  const p = priority.toLowerCase()
  if (p === 'critical') return styles.priorityCritical
  if (p === 'high') return styles.priorityHigh
  if (p === 'medium') return styles.priorityMedium
  return styles.priorityLow
}

function categoryIcon(category: string): string {
  const c = category.toLowerCase()
  if (c === 'remediate') return '🛠'
  if (c === 'investigate') return '🔍'
  if (c === 'optimize') return '⚡'
  if (c === 'review') return '📝'
  return '💡'
}

function EvidenceBlock({ rec }: { rec: Recommendation }) {
  // Parse evidence from description heuristics
  const hasOccurrences = rec.description.match(/(\d+) times?/)
  const hasRate = rec.description.match(/(\d+)%/)
  const hasAction = rec.description.match(/Consider (.+)\./)

  const trust = rec.trust_score ?? 0
  const conf = rec.confidence ?? 0
  const base = rec.base_confidence ?? 0
  const modifier = rec.adaptive_modifier ?? 1.0

  // Highlight divergence: high confidence + low trust is concerning
  const divergent = conf > 0.80 && trust < 0.40

  return (
    <div className={styles.evidence}>
      <div className={`${styles.evidenceRow} ${divergent ? styles.evidenceAlert : ''}`}>
        <span className={styles.evidenceLabel}>Confidence</span>
        <span className={styles.evidenceValue}>{Math.round(conf * 100)}%</span>
        {base !== conf && (
          <span className={styles.evidenceSub}>
            (base {Math.round(base * 100)}% × {modifier.toFixed(2)})
          </span>
        )}
      </div>
      <div className={`${styles.evidenceRow} ${divergent ? styles.evidenceAlert : ''}`}>
        <span className={styles.evidenceLabel}>Trust</span>
        <span className={styles.evidenceValue}>{Math.round(trust * 100)}%</span>
        {divergent && (
          <span className={styles.evidenceAlertText}>Divergence</span>
        )}
      </div>
      {hasOccurrences && (
        <div className={styles.evidenceRow}>
          <span className={styles.evidenceLabel}>Occurrences</span>
          <span className={styles.evidenceValue}>{hasOccurrences[1]}</span>
        </div>
      )}
      {hasRate && (
        <div className={styles.evidenceRow}>
          <span className={styles.evidenceLabel}>Rate</span>
          <span className={styles.evidenceValue}>{hasRate[1]}%</span>
        </div>
      )}
      {hasAction && (
        <div className={styles.evidenceRow}>
          <span className={styles.evidenceLabel}>Suggested Action</span>
          <span className={styles.evidenceValue}>{hasAction[1]}</span>
        </div>
      )}
    </div>
  )
}

function FeedbackButtons({ recId }: { recId: string }) {
  const [state, setState] = useState<'idle' | 'accept' | 'reject' | 'dismiss' | 'error'>('idle')

  const send = async (action: 'accept' | 'reject' | 'dismiss') => {
    setState(action)
    try {
      const res = await fetch('/api/uar/recommendations/feedback', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ recommendation_id: recId, action }),
      })
      if (!res.ok) {
        setState('error')
      }
    } catch {
      setState('error')
    }
  }

  if (state === 'accept') {
    return <div className={styles.feedbackRow}><span className={styles.feedbackOk}>Accepted</span></div>
  }
  if (state === 'reject') {
    return <div className={styles.feedbackRow}><span className={styles.feedbackNo}>Rejected</span></div>
  }
  if (state === 'dismiss') {
    return <div className={styles.feedbackRow}><span className={styles.feedbackMuted}>Dismissed</span></div>
  }

  return (
    <div className={styles.feedbackRow}>
      <button className={styles.feedbackBtnAccept} onClick={() => send('accept')}>Accept</button>
      <button className={styles.feedbackBtnReject} onClick={() => send('reject')}>Reject</button>
      <button className={styles.feedbackBtnDismiss} onClick={() => send('dismiss')}>Dismiss</button>
      {state === 'error' && <span className={styles.feedbackNo}>Failed</span>}
    </div>
  )
}

interface RecommendationPanelProps {
  onOpenReplay?: (runId: string) => void
}

export function RecommendationPanel({ onOpenReplay }: RecommendationPanelProps) {
  const { data, loading, error } = useApiFetch<RecommendationsResponse>(
    '/api/uar/recommendations?hours=24&limit=1000'
  )

  if (loading) return <div className={styles.loading}>Loading recommendations…</div>
  if (error) return <div className={styles.error}>Recommendations failed: {error}</div>
  if (!data || data.recommendations.length === 0) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.panelTitle}>Operational Recommendations</h4>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>✓</div>
          <div className={styles.emptyText}>No recommendations at this time.</div>
          <div className={styles.emptySubtext}>
            {data?.runs_analyzed ?? 0} runs analyzed in the last {data?.hours ?? 24}h.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h4 className={styles.panelTitle}>Operational Recommendations</h4>
        <span className={styles.meta}>
          {data.recommendations.length} from {data.runs_analyzed} runs
        </span>
      </div>

      <div className={styles.recommendationList}>
        {data.recommendations.map((rec) => (
          <div
            key={rec.recommendation_id}
            className={`${styles.recommendationCard} ${priorityClass(rec.priority)}`}
          >
            <div className={styles.cardHeader}>
              <span className={styles.categoryIcon}>{categoryIcon(rec.category)}</span>
              <span className={styles.priorityBadge}>{rec.priority}</span>
              <span className={styles.sourceTag}>{rec.source}</span>
            </div>

            <div className={styles.cardTitle}>{rec.title}</div>
            <div className={styles.cardDescription}>{rec.description}</div>

            <EvidenceBlock rec={rec} />

            {rec.affected_runs.length > 0 && (
              <div className={styles.affectedRuns}>
                <span className={styles.affectedLabel}>Affected runs:</span>
                {onOpenReplay ? (
                  <div className={styles.affectedRunList}>
                    {rec.affected_runs.map((runId) => (
                      <button
                        key={runId}
                        className={styles.affectedRunLink}
                        onClick={() => onOpenReplay(runId)}
                        title={`Open replay for ${runId}`}
                      >
                        {runId.slice(0, 8)}…
                      </button>
                    ))}
                  </div>
                ) : (
                  <span className={styles.affectedCount}>{rec.affected_runs.length}</span>
                )}
              </div>
            )}

            <FeedbackButtons recId={rec.recommendation_id} />
          </div>
        ))}
      </div>
    </div>
  )
}
