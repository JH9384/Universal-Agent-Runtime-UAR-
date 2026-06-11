export interface TrustMovementRecord {
  recommendation_id: string
  run_id?: string | null
  before?: number | null
  after?: number | null
  delta?: number | null
  outcome_type?: string | null
  evidence_refs?: string[]
}

interface TrustMovementPreviewProps {
  recommendationIds: string[]
  runId?: string | null
  movements?: TrustMovementRecord[]
}

function formatScore(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(2)
    : 'unknown'
}

function formatDelta(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'unknown'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}`
}

export function TrustMovementPreview({
  recommendationIds,
  runId,
  movements = [],
}: TrustMovementPreviewProps) {
  const visible = movements.filter((movement) => {
    const matchesRecommendation =
      recommendationIds.length === 0 ||
      recommendationIds.includes(movement.recommendation_id)
    const matchesRun = !runId || !movement.run_id || movement.run_id === runId
    return matchesRecommendation && matchesRun
  })

  return (
    <section className="mc-briefing-section" aria-label="Trust movement preview">
      <h3>Trust movement</h3>
      <p className="mc-subtext">
        Read-only preview of recommendation trust movement linked to this operator evidence path.
      </p>

      {visible.length === 0 ? (
        <p className="mc-status-summary--warn">
          No trust movement is available yet for this recommendation/run linkage.
        </p>
      ) : (
        <ul className="mc-signal-list">
          {visible.map((movement) => (
            <li
              key={`${movement.recommendation_id}:${movement.run_id ?? 'no-run'}`}
              className="mc-signal-card"
            >
              <div className="mc-row">
                <strong>{movement.recommendation_id}</strong>
                <span className="mc-status-badge">
                  {movement.outcome_type ?? 'unknown'}
                </span>
              </div>
              <p className="mc-meta--xs">
                Run: {movement.run_id ?? runId ?? 'unknown'}
              </p>
              <p className="mc-meta--xs">
                Trust: {formatScore(movement.before)} → {formatScore(movement.after)}
                {' '}({formatDelta(movement.delta)})
              </p>
              {movement.evidence_refs && movement.evidence_refs.length > 0 && (
                <p className="mc-meta--xs">
                  Evidence: {movement.evidence_refs.join(', ')}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
