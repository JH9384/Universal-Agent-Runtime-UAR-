import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './MaintenanceWindowPanel.module.css'

interface MaintenanceWindow {
  id: string
  start_at: number
  end_at: number
  description: string
  created_by: string
  created_at: number
}

interface MaintenanceData {
  windows: MaintenanceWindow[]
  active: MaintenanceWindow | null
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

export default function MaintenanceWindowPanel() {
  const { data, loading, error, refetch } = useApiFetch<MaintenanceData>(
    '/api/uar/maintenance',
    { interval: 15_000 }
  )
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    id: '',
    start: '',
    end: '',
    description: '',
  })
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setActionError(null)
    if (!form.id || !form.start || !form.end) return
    const startTs = new Date(form.start).getTime() / 1000
    const endTs = new Date(form.end).getTime() / 1000
    if (endTs <= startTs) {
      setActionError('End time must be after start time')
      return
    }
    setSaving(true)
    try {
      const res = await fetch('/api/uar/maintenance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
        body: JSON.stringify({
          wid: form.id,
          start_at: startTs,
          end_at: endTs,
          description: form.description,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setShowForm(false)
      setForm({ id: '', start: '', end: '', description: '' })
      refetch()
    } catch (err) {
      setActionError(`Save failed: ${String(err)}`)
    } finally {
      setSaving(false)
    }
  }

  async function handleCancel(wid: string) {
    if (!confirm(`Cancel maintenance window "${wid}"?`)) return
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/maintenance/${encodeURIComponent(wid)}`, {
        method: 'DELETE',
        headers: {
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      refetch()
    } catch (err) {
      setActionError(`Cancel failed: ${String(err)}`)
    }
  }

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const windows = data?.windows ?? []
  const active = data?.active

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Maintenance Windows</h3>
        <div className={styles.actions}>
          {active && (
            <span className={`${styles.badge} ${styles.activeBadge}`}>
              Active: {active.id}
            </span>
          )}
          <button className={styles.addBtn} onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : 'Schedule'}
          </button>
        </div>
      </div>

      {actionError && (
        <div className={`${styles.toast} ${styles.errorBanner}`}>{actionError}</div>
      )}

      {showForm && (
        <form className={styles.form} onSubmit={handleSave}>
          <input
            className={styles.input}
            placeholder="Window ID"
            value={form.id}
            onChange={(e) => setForm({ ...form, id: e.target.value })}
            required
          />
          <input
            className={styles.input}
            type="datetime-local"
            aria-label="Start time"
            value={form.start}
            onChange={(e) => setForm({ ...form, start: e.target.value })}
            required
          />
          <input
            className={styles.input}
            type="datetime-local"
            aria-label="End time"
            value={form.end}
            onChange={(e) => setForm({ ...form, end: e.target.value })}
            required
          />
          <input
            className={styles.input}
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <button className={styles.saveBtn} type="submit" disabled={saving}>
            {saving ? '...' : 'Save'}
          </button>
        </form>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Start</th>
              <th>End</th>
              <th>Description</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {windows.map((w) => {
              const isActive = w.start_at <= Date.now() / 1000 && w.end_at >= Date.now() / 1000
              return (
                <tr key={w.id} className={isActive ? styles.rowActive : ''}>
                  <td className={styles.mono}>{w.id}</td>
                  <td>{formatTs(w.start_at)}</td>
                  <td>{formatTs(w.end_at)}</td>
                  <td>{w.description}</td>
                  <td>
                    <span className={`${styles.dot} ${isActive ? styles.dotRed : styles.dotGreen}`} />
                    {isActive ? 'Active' : 'Scheduled'}
                  </td>
                  <td>
                    <button
                      className={`${styles.actionBtn} ${styles.danger}`}
                      onClick={() => handleCancel(w.id)}
                    >
                      Cancel
                    </button>
                  </td>
                </tr>
              )
            })}
            {windows.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>No maintenance windows scheduled</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
