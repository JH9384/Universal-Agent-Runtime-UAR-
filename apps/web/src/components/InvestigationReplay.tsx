import { useRef, useState, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './InvestigationReplay.module.css'

interface Action {
  timestamp: number
  type: string
  description: string
  data?: Record<string, unknown>
}

interface Investigation {
  id: string
  title: string
  run_id?: string
  incident_id?: string
  started_at: number
  ended_at?: number
  status: string
  actions: Action[]
}

export function InvestigationReplay({
  onOpenReplay,
}: {
  onOpenReplay?: (runId: string) => void
}) {
  const { data, loading, error, refetch } = useApiFetch<Investigation[]>(
    '/api/uar/investigations',
    { interval: 30_000 }
  )
  const [selected, setSelected] = useState<Investigation | null>(null)
  const [title, setTitle] = useState('')
  const [runId, setRunId] = useState('')

  const sessions = data ?? []
  const [actionError, setActionError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])
  const createInFlightRef = useRef(false)
  const endInFlightRef = useRef<string | null>(null)

  const handleCreate = async () => {
    if (createInFlightRef.current) return
    createInFlightRef.current = true
    setActionError(null)
    try {
      const res = await fetch('/api/uar/investigations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ title: title || 'Untitled', run_id: runId || undefined }),
      })
      if (!res.ok) throw new Error(`Create failed: ${res.status}`)
      if (!mountedRef.current) return
      setTitle('')
      setRunId('')
      refetch()
    } catch (e) {
      if (mountedRef.current) {
        setActionError(e instanceof Error ? e.message : 'Failed to start investigation')
      }
    } finally {
      createInFlightRef.current = false
    }
  }

  const handleEnd = async (inv: Investigation) => {
    if (endInFlightRef.current === inv.id) return
    endInFlightRef.current = inv.id
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/investigations/${encodeURIComponent(inv.id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ status: 'closed', ended_at: Math.floor(Date.now() / 1000) }),
      })
      if (!res.ok) throw new Error(`End failed: ${res.status}`)
      if (!mountedRef.current) return
      refetch()
    } catch (e) {
      if (mountedRef.current) {
        setActionError(e instanceof Error ? e.message : 'Failed to end investigation')
      }
    } finally {
      endInFlightRef.current = null
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Investigation Replay</h4>
      </div>

      <div className={styles.createForm}>
        <input className={styles.input} placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input className={styles.input} placeholder="Run ID (optional)" value={runId} onChange={(e) => setRunId(e.target.value)} />
        <button className={styles.createBtn} onClick={handleCreate}>Start Investigation</button>
      </div>

      {actionError && <div className={styles.error}>{actionError}</div>}
      {loading && <div className={styles.loading}>Loading…</div>}
      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.sessionList}>
        {sessions.map((inv) => (
          <div key={inv.id} className={`${styles.sessionCard} ${inv.status === 'closed' ? styles.sessionClosed : ''}`}>
            <div className={styles.sessionHeader}>
              <span className={styles.sessionId}>{inv.id}</span>
              <span className={`${styles.statusBadge} ${inv.status === 'active' ? styles.statusActive : styles.statusClosed}`}>{inv.status}</span>
            </div>
            <div className={styles.sessionTitle}>{inv.title}</div>
            {inv.run_id && (
              <button className={styles.linkBtn} onClick={() => onOpenReplay?.(inv.run_id!)}>
                Run: {inv.run_id}
              </button>
            )}
            <div className={styles.sessionMeta}>
              {inv.actions.length} action(s) · {new Date(inv.started_at * 1000).toLocaleString()}
            </div>
            <div className={styles.sessionActions}>
              <button className={styles.viewBtn} onClick={() => setSelected(inv)}>
                {selected?.id === inv.id ? 'Hide Replay' : 'Replay'}
              </button>
              {inv.status === 'active' && (
                <button className={styles.endBtn} onClick={() => handleEnd(inv)}>End</button>
              )}
            </div>

            {selected?.id === inv.id && (
              <div className={styles.replayPanel}>
                <h5 className={styles.replayTitle}>Action Replay</h5>
                {inv.actions.length === 0 && <div className={styles.noActions}>No actions recorded yet.</div>}
                {inv.actions.map((a) => (
                  <div key={`${a.timestamp}-${a.type}`} className={styles.actionRow}>
                    <span className={styles.actionTime}>{new Date(a.timestamp * 1000).toLocaleTimeString()}</span>
                    <span className={styles.actionType}>{a.type}</span>
                    <span className={styles.actionDesc}>{a.description}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {sessions.length === 0 && !loading && (
        <div className={styles.emptyState}>No investigations yet. Start one above.</div>
      )}
    </div>
  )
}
