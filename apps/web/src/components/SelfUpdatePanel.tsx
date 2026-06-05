import { useApiFetch } from '../hooks/useApiFetch'
import styles from './SelfUpdatePanel.module.css'

interface UpdateStatus {
  current_version: string
  latest_version: string
  update_available: boolean
  source: string
  last_checked_at: number
  error: string | null
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

export default function SelfUpdatePanel() {
  const { data, loading, error } = useApiFetch<UpdateStatus>(
    '/api/uar/update/status',
    { interval: 0 }
  )

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Checking...</span></div>
  }

  if (error) {
    return <div className={styles.panel}><span className={styles.error}>Error: {error}</span></div>
  }

  const status = data

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>UAR Version</h3>
        {status?.update_available && (
          <span className={styles.updateBadge}>Update Available</span>
        )}
      </div>

      <div className={styles.grid}>
        <div className={styles.row}>
          <span className={styles.label}>Current</span>
          <span className={styles.value}>{status?.current_version || 'unknown'}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>Latest</span>
          <span className={styles.value}>{status?.latest_version || 'unknown'}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>Source</span>
          <span className={styles.value}>{status?.source || 'unknown'}</span>
        </div>
        <div className={styles.row}>
          <span className={styles.label}>Checked</span>
          <span className={styles.value}>
            {status?.last_checked_at ? formatTs(status.last_checked_at) : '—'}
          </span>
        </div>
      </div>

      {status?.error && (
        <div className={styles.errorBox}>{status.error}</div>
      )}

      {status?.update_available && (
        <div className={styles.hint}>
          Run <code>pip install --upgrade universal-agent-runtime</code> to update.
        </div>
      )}
    </div>
  )
}
