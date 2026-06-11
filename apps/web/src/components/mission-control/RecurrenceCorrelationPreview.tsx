export interface RecurrenceCorrelationRecord {
  recommendation_id: string
  run_id?: string | null
  outcome_type?: string | null
  evidence_refs?: string[]
  trust_delta?: number | null
  later_recurrence_count: number
  later_recurrence_run_ids: string[]
  correlation_status: 'improved' | 'recurred' | 'unknown'
}

interface RecurrenceCorrelationPreviewProps {
  recommendationIds: string[]
  runId?: string | null
  correlations?: RecurrenceCorrelationRecord[]
}

function formatDelta(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'unknown'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}`
}

function statusText(status: RecurrenceCorrelationRecord['correlation_status']): string {
  if (status === 'improved') return 'Improved'
  if (status === 'recurred') return 'Recurred'
  return 'Unknown'
}

export function RecurrenceCorrelationPreview({
  recommendationIds,
  runId,
  correlations = [],
}: RecurrenceCorrelationPreviewProps) {
  const visible = correlations.filter((item) => {
    const matchesRecommendation =
      recommendationIds.length === 0 ||
      recommendationIds.includes(item.recommendation_id)
    const matchesRun = !runId || !item.run_id || item.run_id === runId
    return matchesRecommendation && matchesRun
  })

  return (
    <section className="mc-briefing-section" aria-label="Recurrence correlation preview">
      <h3>Recurrence correlation</h3>
      <p className="mc-subtext">
        Read-only preview showing whether trust movement and outcome capture were followed by later recurrence.
      </p>

      {visible.length === 0 ? (
        <p className="mc-status-summary--warn">
          No recurrence correlation is available yet for this recommendation/run linkage.
        </p>
      ) : (
        <ul className="mc-signal-list">
          {visible.map((item) => (
            <li
              key={`${item.recommendation_id}:${item.run_id ?? 'no-run'}`}
              className="mc-signal-card"
            >
              <div className="mc-row">
                <strong>{item.recommendation_id}</strong>
                <span className="mc-status-badge">
                  {statusText(item.correlation_status)}
                </span>
              </div>
              <p className="mc-meta--xs">
                Run: {item.run_id ?? runId ?? 'unknown'}
              </p>
              <p className="mc-meta--xs">
                Outcome: {item.outcome_type ?? 'unknown'}
              </p>
              <p className="mc-meta--xs">
                Trust delta: {formatDelta(item.trust_delta)}
              </p>
              <p className="mc-meta--xs">
                Later recurrence: {item.later_recurrence_count}
              </p>
              {item.later_recurrence_run_ids.length > 0 && (
                <p className="mc-meta--xs">
                  Later runs: {item.later_recurrence_run_ids.join(', ')}
                </p>
              )}
              {item.evidence_refs && item.evidence_refs.length > 0 && (
                <p className="mc-meta--xs">
                  Evidence: {item.evidence_refs.join(', ')}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
