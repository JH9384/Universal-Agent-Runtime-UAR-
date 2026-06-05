import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './DataSourceRegistryPanel.module.css'

interface DataSource {
  id: string
  source_type: string
  location: string
  description: string
  healthy: boolean
  last_check_at: number | null
  error: string | null
}

interface DataSourceData {
  sources: DataSource[]
  total: number
  healthy: number
}

const SOURCE_TYPE_ICONS: Record<string, string> = {
  postgres: '🐘',
  sqlite: '🪶',
  json: '📁',
  autonomi: '🔗',
  api: '🌐',
}

export default function DataSourceRegistryPanel() {
  const { data, loading, error, refetch } = useApiFetch<DataSourceData>(
    '/api/uar/data-sources',
    { interval: 30_000 }
  )
  const [checking, setChecking] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ id: '', source_type: 'api', location: '', description: '' })
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleCheck(dsid: string) {
    setChecking(dsid)
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/data-sources/${encodeURIComponent(dsid)}/check`, {
        method: 'POST',
        headers: {
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      refetch()
    } catch (e) {
      setActionError(`Check failed: ${String(e)}`)
    } finally {
      setChecking(null)
    }
  }

  async function handleDelete(dsid: string) {
    if (!confirm(`Remove data source "${dsid}"?`)) return
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/data-sources/${encodeURIComponent(dsid)}`, {
        method: 'DELETE',
        headers: {
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      refetch()
    } catch (e) {
      setActionError(`Remove failed: ${String(e)}`)
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setActionError(null)
    if (!form.id || !form.location) return
    setSaving(true)
    try {
      const res = await fetch('/api/uar/data-sources', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
        body: JSON.stringify({
          dsid: form.id,
          source_type: form.source_type,
          location: form.location,
          description: form.description,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setShowForm(false)
      setForm({ id: '', source_type: 'api', location: '', description: '' })
      refetch()
    } catch (err) {
      setActionError(`Save failed: ${String(err)}`)
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading...</span></div>
  }
  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const sources = data?.sources ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Data Sources</h3>
        <div className={styles.actions}>
          <span className={styles.meta}>
            {data?.healthy ?? 0}/{data?.total ?? 0} healthy
          </span>
          <button className={styles.addBtn} onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : 'Add'}
          </button>
        </div>
      </div>

      {actionError && (
        <div className={`${styles.toast} ${styles.errorBanner}`}>{actionError}</div>
      )}

      {showForm && (
        <form className={styles.form} onSubmit={handleSave}>
          <input className={styles.input} placeholder="ID" value={form.id}
            onChange={(e) => setForm({ ...form, id: e.target.value })} required />
          <select className={styles.select} aria-label="Source type"
            value={form.source_type}
            onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
            <option value="postgres">PostgreSQL</option>
            <option value="sqlite">SQLite</option>
            <option value="json">JSONL</option>
            <option value="autonomi">Autonomi</option>
            <option value="api">API</option>
          </select>
          <input className={styles.input} placeholder="Location (URL/path)" value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })} required />
          <input className={styles.input} placeholder="Description" value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <button className={styles.saveBtn} type="submit" disabled={saving}>
            {saving ? '...' : 'Save'}
          </button>
        </form>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>Type</th><th>ID</th><th>Location</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} className={s.healthy ? '' : styles.rowError} title={s.error || undefined}>
                <td>{SOURCE_TYPE_ICONS[s.source_type] || '❓'} {s.source_type}</td>
                <td className={styles.mono}>{s.id}</td>
                <td className={styles.location}>{s.location}</td>
                <td>
                  <span className={`${styles.dot} ${s.healthy ? styles.dotGreen : styles.dotRed}`} />
                  {s.healthy ? 'OK' : 'Error'}
                </td>
                <td>
                  <button className={styles.actionBtn} onClick={() => handleCheck(s.id)} disabled={checking === s.id}>
                    {checking === s.id ? '...' : 'Check'}
                  </button>
                  <button className={`${styles.actionBtn} ${styles.danger}`} onClick={() => handleDelete(s.id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan={5} className={styles.empty}>No data sources registered</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
