import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './CredentialVaultPanel.module.css'

interface CredentialEntry {
  id: string
  name: string
  service_type: string
  encrypted_value: string
  created_at: number
  updated_at: number
  last_tested_at: number | null
  last_test_status: string | null
  metadata: Record<string, unknown>
}

interface CredentialData {
  credentials: CredentialEntry[]
  total: number
  encrypted_at_rest: boolean
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

const SERVICE_TYPES = ['ollama', 'autonomi', 'openai', 'generic']

export default function CredentialVaultPanel() {
  const { data, loading, error, refetch } = useApiFetch<CredentialData>(
    '/api/uar/credentials',
    { interval: 30_000 }
  )
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    id: '',
    name: '',
    service_type: 'generic',
    value: '',
  })
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setActionError(null)
    if (!form.id || !form.name || !form.value) return
    setSaving(true)
    try {
      const res = await fetch('/api/uar/credentials', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
        body: JSON.stringify({
          cred_id: form.id,
          name: form.name,
          service_type: form.service_type,
          value: form.value,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setShowForm(false)
      setForm({ id: '', name: '', service_type: 'generic', value: '' })
      refetch()
    } catch (e) {
      setActionError(`Save failed: ${String(e)}`)
    } finally {
      setSaving(false)
    }
  }

  async function handleTest(credId: string) {
    setTesting(credId)
    setTestResult(null)
    try {
      const res = await fetch(`/api/uar/credentials/${encodeURIComponent(credId)}/test`, {
        method: 'POST',
        headers: {
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
      })
      const json = await res.json()
      setTestResult(`${json.ok ? 'OK' : 'FAIL'}: ${json.message}`)
      refetch()
    } catch (e) {
      setTestResult(`Error: ${String(e)}`)
    } finally {
      setTesting(null)
    }
  }

  async function handleDelete(credId: string) {
    if (!confirm(`Delete credential "${credId}"?`)) return
    setActionError(null)
    try {
      const res = await fetch(`/api/uar/credentials/${encodeURIComponent(credId)}`, {
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
      setActionError(`Delete failed: ${String(e)}`)
    }
  }

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading credentials...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const creds = data?.credentials ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Credential Vault</h3>
        <div className={styles.actions}>
          <span className={styles.meta}>
            {data?.encrypted_at_rest ? 'Encrypted' : 'Plaintext'}
          </span>
          <button className={styles.addBtn} onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : 'Add'}
          </button>
        </div>
      </div>

      {actionError && (
        <div className={`${styles.toast} ${styles.errorBanner}`}>{actionError}</div>
      )}

      {testResult && (
        <div className={styles.toast}>{testResult}</div>
      )}

      {showForm && (
        <form className={styles.form} onSubmit={handleSave}>
          <input
            className={styles.input}
            placeholder="ID (e.g. ollama_prod)"
            value={form.id}
            onChange={(e) => setForm({ ...form, id: e.target.value })}
            required
          />
          <input
            className={styles.input}
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <select
            className={styles.select}
            aria-label="Service type"
            value={form.service_type}
            onChange={(e) => setForm({ ...form, service_type: e.target.value })}
          >
            {SERVICE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <input
            className={styles.input}
            placeholder="Value (API key, URL, etc.)"
            value={form.value}
            onChange={(e) => setForm({ ...form, value: e.target.value })}
            required
            type="password"
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
              <th>Name</th>
              <th>Type</th>
              <th>Updated</th>
              <th>Last Test</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {creds.map((c) => (
              <tr key={c.id}>
                <td className={styles.mono}>{c.id}</td>
                <td>{c.name}</td>
                <td>{c.service_type}</td>
                <td>{formatTs(c.updated_at)}</td>
                <td>
                  {c.last_tested_at
                    ? `${c.last_test_status} · ${formatTs(c.last_tested_at)}`
                    : '—'}
                </td>
                <td>
                  <button
                    className={styles.actionBtn}
                    onClick={() => handleTest(c.id)}
                    disabled={testing === c.id}
                  >
                    {testing === c.id ? '...' : 'Test'}
                  </button>
                  <button
                    className={`${styles.actionBtn} ${styles.danger}`}
                    onClick={() => handleDelete(c.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {creds.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>No credentials stored</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
