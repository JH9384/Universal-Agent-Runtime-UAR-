import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './SyncStatusPanel.module.css'

interface StoreSyncStatus {
  store_id: string
  store_type: string
  last_write_at: number | null
  last_read_at: number | null
  record_count: number
  healthy: boolean
  lag_seconds: number
  error: string | null
}

interface SyncHealthData {
  overall_healthy: boolean
  stores: StoreSyncStatus[]
  checked_at: number
}

function formatTs(ts: number | null): string {
  if (!ts) return 'never'
  const d = new Date(ts * 1000)
  return d.toLocaleString()
}

function lagText(seconds: number): string {
  if (seconds < 1) return '< 1s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

export default function SyncStatusPanel() {
  const { data, loading, error, refetch } = useApiFetch<SyncHealthData>(
    '/api/uar/sync/status',
    { interval: 15_000 }
  )
  const [resyncing, setResyncing] = useState<string | null>(null)
  const [resyncResult, setResyncResult] = useState<string | null>(null)

  async function handleResync(targetId: string) {
    setResyncing(targetId)
    setResyncResult(null)
    try {
      const res = await fetch('/api/uar/sync/resync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
        body: JSON.stringify({ target: targetId }),
      })
      const json = await res.json()
      if (json.success) {
        setResyncResult(`Resynced ${json.copied} records to ${targetId}`)
      } else {
        setResyncResult(`Error: ${json.error}`)
      }
      refetch()
    } catch (e) {
      setResyncResult(`Error: ${String(e)}`)
    } finally {
      setResyncing(null)
    }
  }

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading sync status...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const stores = data?.stores ?? []
  const overall = data?.overall_healthy ?? false

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Sync Status</h3>
        <span className={`${styles.badge} ${overall ? styles.healthy : styles.unhealthy}`}>
          {overall ? 'Healthy' : 'Degraded'}
        </span>
      </div>

      {resyncResult && (
        <div className={styles.toast}>{resyncResult}</div>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Store</th>
              <th>Type</th>
              <th>Records</th>
              <th>Last Write</th>
              <th>Last Read</th>
              <th>Lag</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {stores.map((s) => (
              <tr key={s.store_id} className={s.healthy ? '' : styles.rowError}>
                <td className={styles.mono}>{s.store_id}</td>
                <td>{s.store_type}</td>
                <td>{s.record_count}</td>
                <td>{formatTs(s.last_write_at)}</td>
                <td>{formatTs(s.last_read_at)}</td>
                <td>{lagText(s.lag_seconds)}</td>
                <td>
                  <span className={`${styles.dot} ${s.healthy ? styles.dotGreen : styles.dotRed}`} />
                  {s.healthy ? 'OK' : 'Error'}
                </td>
                <td>
                  <button
                    className={styles.resyncBtn}
                    onClick={() => handleResync(s.store_id)}
                    disabled={resyncing === s.store_id}
                  >
                    {resyncing === s.store_id ? '...' : 'Resync'}
                  </button>
                </td>
              </tr>
            ))}
            {stores.length === 0 && (
              <tr>
                <td colSpan={8} className={styles.empty}>No stores registered</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className={styles.footer}>
        Checked at {data?.checked_at ? formatTs(data.checked_at) : '—'}
      </div>
    </div>
  )
}
