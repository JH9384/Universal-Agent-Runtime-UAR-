import { useState, useRef, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './InvestigationFlow.module.css'

interface FlowStep {
  step: number
  title: string
  type: string
  description: string
  action: string
  link?: string
  items?: { title?: string; id?: string; rec_id?: string; status?: string }[]
  suggested_title?: string
}

interface FlowData {
  run_id: string
  steps: FlowStep[]
  generated_at: number
}

export function InvestigationFlow({
  runId,
  onOpenReplay,
  onOpenIncident,
  onOpenGraph,
}: {
  runId?: string
  onOpenReplay?: (runId: string) => void
  onOpenIncident?: () => void
  onOpenGraph?: (runId: string) => void
}) {
  const [inputRunId, setInputRunId] = useState(runId ?? '')
  const [activeRunId, setActiveRunId] = useState(runId ?? '')
  const [completed, setCompleted] = useState<Set<number>>(new Set())
  const [snapshotError, setSnapshotError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const snapshotInFlightRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const { data, loading, error } = useApiFetch<FlowData>(
    activeRunId ? `/api/uar/investigate/${encodeURIComponent(activeRunId)}` : ''
  )

  const handleSearch = () => {
    if (inputRunId.trim()) setActiveRunId(inputRunId.trim())
  }

  const handleAction = (step: FlowStep) => {
    if (step.type === 'replay') {
      onOpenReplay?.(activeRunId)
    } else if (step.type === 'incidents' || step.type === 'incident_action') {
      onOpenIncident?.()
    } else if (step.type === 'graph') {
      onOpenGraph?.(activeRunId)
    } else if (step.type === 'snapshot') {
      if (snapshotInFlightRef.current) return
      snapshotInFlightRef.current = true
      setSnapshotError(null)
      fetch('/api/uar/snapshots', { method: 'POST', headers: authHeaders() })
        .then((res) => {
          if (!res.ok) throw new Error(`Snapshot failed: ${res.status}`)
          if (mountedRef.current) setCompleted((prev) => new Set(prev).add(step.step))
        })
        .catch((err: unknown) => {
          if (mountedRef.current) setSnapshotError(err instanceof Error ? err.message : 'Snapshot failed')
        })
        .finally(() => {
          snapshotInFlightRef.current = false
        })
      return
    }
    setCompleted((prev) => new Set(prev).add(step.step))
  }

  const steps = data?.steps ?? []
  const allDone = steps.length > 0 && steps.every((s) => completed.has(s.step))

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Unified Investigation</h4>
        <div className={styles.searchRow}>
          <input
            className={styles.searchInput}
            placeholder="Run ID"
            value={inputRunId}
            onChange={(e) => setInputRunId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button className={styles.searchBtn} onClick={handleSearch}>
            Investigate
          </button>
        </div>
      </div>

      {loading && <div className={styles.loading}>Building flow…</div>}
      {error && <div className={styles.error}>{error}</div>}
      {snapshotError && <div className={styles.error}>{snapshotError}</div>}

      {allDone && (
        <div className={styles.completeBanner}>
          Investigation complete for {activeRunId}.
        </div>
      )}

      {steps.length > 0 && (
        <div className={styles.stepList}>
          {steps.map((s) => {
            const done = completed.has(s.step)
            return (
              <div key={s.step} className={`${styles.stepCard} ${done ? styles.stepDone : ''}`}>
                <div className={styles.stepNumber}>{s.step}</div>
                <div className={styles.stepBody}>
                  <div className={styles.stepTitle}>{s.title}</div>
                  <div className={styles.stepDesc}>{s.description}</div>
                  {s.items && s.items.length > 0 && (
                    <ul className={styles.stepItems}>
                      {s.items.map((it, i) => (
                        <li key={it.id || it.rec_id || `${it.title || 'item'}-${i}`}>
                          {it.title || it.id || it.rec_id}
                          {it.status && <span className={styles.itemStatus}> ({it.status})</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    className={`${styles.actionBtn} ${done ? styles.actionDone : ''}`}
                    onClick={() => handleAction(s)}
                  >
                    {done ? 'Done' : s.action}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {activeRunId && steps.length === 0 && !loading && (
        <div className={styles.emptyState}>
          No investigation steps found for {activeRunId}.
        </div>
      )}
    </div>
  )
}
