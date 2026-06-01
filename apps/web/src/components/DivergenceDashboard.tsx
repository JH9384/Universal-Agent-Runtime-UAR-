import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './DivergenceDashboard.module.css'

interface DivergenceItem {
  recommendation_id: string
  title: string
  category: string
  source: string
  confidence: number
  trust_score: number
  base_confidence: number
  adaptive_modifier: number
  drift_penalty: number
  affected_runs: string[]
}

interface DivergenceData {
  high_confidence_low_trust: DivergenceItem[]
  low_confidence_high_trust: DivergenceItem[]
}

interface RecommendationsResponse {
  recommendations: any[]
  generated_at: number
  hours: number
  runs_analyzed: number
}

export function DivergenceDashboard({ onOpenReplay }: { onOpenReplay?: (runId: string) => void }) {
  const { data, loading, error } = useApiFetch<RecommendationsResponse>(
    '/api/uar/recommendations?hours=24&limit=1000'
  )

  const [expanded, setExpanded] = useState<'none' | 'high_low' | 'low_high'>('none')

  if (loading) return <div className={styles.loading}>Loading divergence…</div>
  if (error) return <div className={styles.error}>Divergence failed: {error}</div>

  // Compute divergence from raw recommendations
  const recommendations = data?.recommendations ?? []
  const highLow = recommendations.filter(
    (r: any) => (r.confidence ?? 0) > 0.90 && (r.trust_score ?? 0) < 0.40
  )
  const lowHigh = recommendations.filter(
    (r: any) => (r.confidence ?? 0) < 0.50 && (r.trust_score ?? 0) > 0.80
  )

  const total = highLow.length + lowHigh.length

  if (total === 0) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.panelTitle}>Divergence Dashboard</h4>
        <div className={styles.emptyState}>No divergence cases detected.</div>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h4 className={styles.panelTitle}>Divergence Dashboard</h4>
        <span className={styles.meta}>{total} case(s)</span>
      </div>

      {/* Summary Cards */}
      <div className={styles.summaryRow}>
        <button
          className={`${styles.summaryCard} ${styles.highLowCard} ${expanded === 'high_low' ? styles.expanded : ''}`}
          onClick={() => setExpanded(expanded === 'high_low' ? 'none' : 'high_low')}
        >
          <div className={styles.summaryNumber}>{highLow.length}</div>
          <div className={styles.summaryLabel}>High Confidence</div>
          <div className={styles.summarySub}>Low Trust</div>
          <div className={styles.summaryHint}>
            confidence &gt; 0.90, trust &lt; 0.40
          </div>
        </button>

        <button
          className={`${styles.summaryCard} ${styles.lowHighCard} ${expanded === 'low_high' ? styles.expanded : ''}`}
          onClick={() => setExpanded(expanded === 'low_high' ? 'none' : 'low_high')}
        >
          <div className={styles.summaryNumber}>{lowHigh.length}</div>
          <div className={styles.summaryLabel}>Low Confidence</div>
          <div className={styles.summarySub}>High Trust</div>
          <div className={styles.summaryHint}>
            confidence &lt; 0.50, trust &gt; 0.80
          </div>
        </button>
      </div>

      {/* Detail Lists */}
      {expanded === 'high_low' && (
        <div className={styles.detailSection}>
          <h5 className={styles.detailTitle}>High Confidence / Low Trust</h5>
          <p className={styles.detailDesc}>
            Likely stale heuristics, overconfident engines, or hidden failure modes.
          </p>
          <div className={styles.itemList}>
            {highLow.map((rec: any) => (
              <DivergenceItemRow
                key={rec.recommendation_id}
                rec={rec}
                onOpenReplay={onOpenReplay}
              />
            ))}
          </div>
        </div>
      )}

      {expanded === 'low_high' && (
        <div className={styles.detailSection}>
          <h5 className={styles.detailTitle}>Low Confidence / High Trust</h5>
          <p className={styles.detailDesc}>
            System knows less than reality. Often the easiest future gains.
          </p>
          <div className={styles.itemList}>
            {lowHigh.map((rec: any) => (
              <DivergenceItemRow
                key={rec.recommendation_id}
                rec={rec}
                onOpenReplay={onOpenReplay}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DivergenceItemRow({
  rec,
  onOpenReplay,
}: {
  rec: any
  onOpenReplay?: (runId: string) => void
}) {
  const conf = rec.confidence ?? 0
  const trust = rec.trust_score ?? 0
  const gap = Math.abs(conf - trust)

  return (
    <div className={styles.itemRow}>
      <div className={styles.itemHeader}>
        <span className={styles.itemTitle}>{rec.title}</span>
        <span className={styles.itemCategory}>{rec.category}</span>
      </div>
      <div className={styles.itemMetrics}>
        <span className={styles.metric}>
          Confidence <strong>{(conf * 100).toFixed(0)}%</strong>
        </span>
        <span className={styles.metric}>
          Trust <strong>{(trust * 100).toFixed(0)}%</strong>
        </span>
        <span className={`${styles.metric} ${styles.gapMetric}`}>
          Gap <strong>{(gap * 100).toFixed(0)}%</strong>
        </span>
      </div>
      {onOpenReplay && rec.affected_runs?.length > 0 && (
        <div className={styles.itemRuns}>
          {rec.affected_runs.map((runId: string) => (
            <button
              key={runId}
              className={styles.runLink}
              onClick={() => onOpenReplay(runId)}
              title={`Open replay for ${runId}`}
            >
              {runId.slice(0, 8)}…
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
