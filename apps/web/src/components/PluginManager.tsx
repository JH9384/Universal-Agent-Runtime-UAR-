import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './PluginManager.module.css'

interface PluginManifest {
  name: string
  source: string
  skill_count: number
  loaded_at: number
  healthy: boolean
  error: string | null
}

interface PluginData {
  plugins: PluginManifest[]
  total: number
  healthy: number
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

export default function PluginManager() {
  const { data, loading, error, refetch } = useApiFetch<PluginData>(
    '/api/uar/plugins',
    { interval: 30_000 }
  )
  const [reloading, setReloading] = useState(false)
  const [reloadResult, setReloadResult] = useState<string | null>(null)

  async function handleReload() {
    setReloading(true)
    setReloadResult(null)
    try {
      const res = await fetch('/api/uar/plugins/reload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('uar_api_key')
            ? { Authorization: `Bearer ${localStorage.getItem('uar_api_key')}` }
            : {}),
        },
      })
      const json = await res.json()
      if (json.success) {
        setReloadResult(`Reloaded ${json.total} plugin(s)`)
      } else {
        setReloadResult('Reload failed')
      }
      refetch()
    } catch (e) {
      setReloadResult(`Error: ${String(e)}`)
    } finally {
      setReloading(false)
    }
  }

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading plugins...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const plugins = data?.plugins ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Plugins</h3>
        <div className={styles.actions}>
          <span className={styles.meta}>
            {data?.healthy ?? 0}/{data?.total ?? 0} healthy
          </span>
          <button
            className={styles.reloadBtn}
            onClick={handleReload}
            disabled={reloading}
          >
            {reloading ? '...' : 'Reload All'}
          </button>
        </div>
      </div>

      {reloadResult && (
        <div className={styles.toast}>{reloadResult}</div>
      )}

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Source</th>
              <th>Skills</th>
              <th>Loaded</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {plugins.map((p) => (
              <tr key={p.name} className={p.healthy ? '' : styles.rowError}>
                <td className={styles.mono} title={p.error || undefined}>{p.name}</td>
                <td>{p.source}</td>
                <td>{p.skill_count}</td>
                <td>{formatTs(p.loaded_at)}</td>
                <td>
                  <span className={`${styles.dot} ${p.healthy ? styles.dotGreen : styles.dotRed}`} />
                  {p.healthy ? 'OK' : 'Error'}
                </td>
              </tr>
            ))}
            {plugins.length === 0 && (
              <tr>
                <td colSpan={5} className={styles.empty}>No plugins loaded</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
