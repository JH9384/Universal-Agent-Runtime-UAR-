import { useRef, useState, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './TimeMachine.module.css'

interface Snapshot {
  timestamp: number
  captured_at: number
  trust: {
    recommendation_types: { type: string; trust_score: number; drift_penalty: number }[]
    system_calibration_error: number
  } | null
  recommendation_count: number
  recent_run_ids: string[]
}

export function TimeMachine({
  onOpenReplay,
}: {
  onOpenReplay?: (runId: string) => void
}) {
  const { data: snapshots, loading, error, refetch } = useApiFetch<Snapshot[]>(
    '/api/uar/snapshots?limit=48'
  )
  const [selected, setSelected] = useState<number | null>(null)
  const [detailUrl, setDetailUrl] = useState<string>('')

  const handleSelect = (ts: number) => {
    setSelected(ts)
    setDetailUrl(`/api/uar/snapshots/${encodeURIComponent(String(ts))}`)
  }

  const { data: detail } = useApiFetch<Snapshot>(detailUrl)

  const [actionError, setActionError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])
  const captureInFlightRef = useRef(false)

  const handleCapture = async () => {
    if (captureInFlightRef.current) return
    captureInFlightRef.current = true
    setActionError(null)
    try {
      const res = await fetch('/api/uar/snapshots', {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!res.ok) throw new Error(`Snapshot failed: ${res.status}`)
      if (!mountedRef.current) return
      refetch()
    } catch (e) {
      if (mountedRef.current) {
        setActionError(e instanceof Error ? e.message : 'Snapshot capture failed')
      }
    } finally {
      captureInFlightRef.current = false
    }
  }

  const list = snapshots ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h4 className={styles.panelTitle}>Time Machine</h4>
          <span className={styles.meta}>{list.length} snapshot(s)</span>
        </div>
        <button className={styles.captureBtn} onClick={handleCapture}>
          Capture Now
        </button>
      </div>

      {loading && <div className={styles.loading}>Loading snapshots…</div>}
      {error && <div className={styles.error}>{error}</div>}
      {actionError && <div className={styles.error}>{actionError}</div>}

      {list.length > 0 && (
        <div className={styles.timeline}>
          {list.map((snap) => {
            const date = new Date(snap.timestamp * 1000)
            const isActive = selected === snap.timestamp
            return (
              <button
                key={snap.timestamp}
                className={`${styles.timelinePoint} ${isActive ? styles.timelinePointActive : ''}`}
                onClick={() => handleSelect(snap.timestamp)}
                title={date.toLocaleString()}
              >
                <div className={styles.timelineDot} />
                <span className={styles.timelineLabel}>
                  {date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
                <span className={styles.timelineTime}>
                  {date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {detail && (
        <div className={styles.detailPanel}>
          <h5 className={styles.detailTitle}>
            {new Date(detail.timestamp * 1000).toLocaleString()}
          </h5>

          <div className={styles.statsRow}>
            <div className={styles.statBox}>
              <span className={styles.statValue}>{detail.recommendation_count}</span>
              <span className={styles.statLabel}>Recommendations</span>
            </div>
            <div className={styles.statBox}>
              <span className={styles.statValue}>
                {detail.trust?.recommendation_types?.length ?? 0}
              </span>
              <span className={styles.statLabel}>Trust Types</span>
            </div>
            <div className={styles.statBox}>
              <span className={styles.statValue}>
                {detail.trust?.system_calibration_error?.toFixed(3) ?? '—'}
              </span>
              <span className={styles.statLabel}>Calibration</span>
            </div>
          </div>

          {detail.trust && detail.trust.recommendation_types.length > 0 && (
            <div className={styles.trustList}>
              <h6 className={styles.trustListTitle}>Trust at this moment</h6>
              {detail.trust.recommendation_types.map((t) => (
                <div key={t.type} className={styles.trustRow}>
                  <span className={styles.trustType}>{t.type}</span>
                  <span className={styles.trustScore}>{t.trust_score.toFixed(2)}</span>
                  {t.drift_penalty > 0 && (
                    <span className={styles.driftBadge}>-{t.drift_penalty}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {detail.recent_run_ids.length > 0 && (
            <div className={styles.runList}>
              <h6 className={styles.runListTitle}>Recent runs</h6>
              <div className={styles.runTags}>
                {detail.recent_run_ids.map((rid) => (
                  <button
                    key={rid}
                    className={styles.runTag}
                    onClick={() => onOpenReplay?.(rid)}
                  >
                    {rid}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {list.length === 0 && !loading && (
        <div className={styles.emptyState}>
          No snapshots yet. Click "Capture Now" to create the first one.
        </div>
      )}
    </div>
  )
}
