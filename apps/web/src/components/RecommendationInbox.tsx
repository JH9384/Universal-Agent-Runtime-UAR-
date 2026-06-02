import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './RecommendationInbox.module.css'

interface InboxItem {
  id: string
  source_rec_id: string
  title: string
  category: string
  confidence: number
  trust_score: number | null
  drift_penalty: number | null
  status: 'new' | 'assigned' | 'investigating' | 'resolved' | 'dismissed'
  assigned_to: string | null
  notes: string
  created_at: number
  updated_at: number
}

const STATUS_OPTIONS = ['new', 'assigned', 'investigating', 'resolved', 'dismissed'] as const

export function RecommendationInbox() {
  const { data, loading, error } = useApiFetch<InboxItem[]>('/api/uar/inbox', { interval: 30_000 })
  const [filter, setFilter] = useState<string>('all')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editNotes, setEditNotes] = useState('')
  const [editAssignee, setEditAssignee] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const items = data ?? []
  const filtered = filter === 'all' ? items : items.filter((i) => i.status === filter)
  const counts = STATUS_OPTIONS.reduce((acc, s) => {
    acc[s] = items.filter((i) => i.status === s).length
    return acc
  }, {} as Record<string, number>)

  const handleUpdate = async (item: InboxItem, status: string) => {
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/inbox/${item.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          status,
          notes: editNotes || item.notes,
          assigned_to: editAssignee || item.assigned_to,
        }),
      })
      if (!res.ok) throw new Error(`Update failed: ${res.status}`)
      window.location.reload()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Update failed')
    }
  }

  if (loading) return <div className={styles.loading}>Loading inbox…</div>
  if (error) return <div className={styles.error}>{error}</div>

  // action error is rendered inline, not as a page-level replacement

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h4 className={styles.panelTitle}>Recommendation Inbox</h4>
          <span className={styles.meta}>{items.length} item(s)</span>
        </div>
      </div>

      {actionError && <div className={styles.error}>{actionError}</div>}

      <div className={styles.filterBar}>
        <button className={`${styles.filterBtn} ${filter === 'all' ? styles.filterActive : ''}`} onClick={() => setFilter('all')}>
          All <span className={styles.filterCount}>{items.length}</span>
        </button>
        {STATUS_OPTIONS.map((s) => (
          <button key={s} className={`${styles.filterBtn} ${filter === s ? styles.filterActive : ''}`} onClick={() => setFilter(s)}>
            {s} <span className={styles.filterCount}>{counts[s] || 0}</span>
          </button>
        ))}
      </div>

      <div className={styles.itemList}>
        {filtered.map((item) => (
          <div key={item.id} className={`${styles.itemCard} ${styles[`status${item.status}`] || ''}`}>
            <div className={styles.itemHeader}>
              <span className={styles.itemId}>{item.source_rec_id}</span>
              <span className={styles.itemCategory}>{item.category}</span>
              <span className={`${styles.statusBadge} ${styles[`badge${item.status}`] || ''}`}>{item.status}</span>
            </div>
            <div className={styles.itemTitle}>{item.title}</div>
            <div className={styles.itemMetrics}>
              <span>Confidence: {(item.confidence * 100).toFixed(0)}%</span>
              <span>Trust: {item.trust_score !== null ? item.trust_score.toFixed(2) : '—'}</span>
              {item.drift_penalty !== null && item.drift_penalty > 0 && (
                <span className={styles.driftBadge}>Drift -{item.drift_penalty}</span>
              )}
            </div>
            {item.assigned_to && (
              <div className={styles.assignee}>Assigned: {item.assigned_to}</div>
            )}
            {item.notes && <div className={styles.notes}>{item.notes}</div>}

            {editingId === item.id ? (
              <div className={styles.editForm}>
                <input className={styles.editInput} placeholder="Assignee" value={editAssignee} onChange={(e) => setEditAssignee(e.target.value)} />
                <textarea className={styles.editTextarea} placeholder="Notes" value={editNotes} onChange={(e) => setEditNotes(e.target.value)} />
                <div className={styles.statusActions}>
                  {STATUS_OPTIONS.map((s) => (
                    <button key={s} className={styles.statusBtn} onClick={() => handleUpdate(item, s)}>
                      Mark {s}
                    </button>
                  ))}
                </div>
                <button className={styles.cancelBtn} onClick={() => setEditingId(null)}>Cancel</button>
              </div>
            ) : (
              <button className={styles.editBtn} onClick={() => { setEditingId(item.id); setEditAssignee(item.assigned_to || ''); setEditNotes(item.notes || '') }}>
                Manage
              </button>
            )}
          </div>
        ))}
      </div>

      {items.length === 0 && <div className={styles.emptyState}>No recommendations in inbox yet.</div>}
    </div>
  )
}
