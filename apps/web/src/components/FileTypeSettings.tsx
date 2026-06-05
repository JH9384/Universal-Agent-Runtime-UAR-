import { useApiFetch } from '../hooks/useApiFetch'
import styles from './FileTypeSettings.module.css'

interface FileTypeData {
  allowed_extensions: string[]
  blocked_extensions: string[]
  whitelist_env_set: boolean
  blocklist_env_set: boolean
}

export default function FileTypeSettings() {
  const { data, loading, error } = useApiFetch<FileTypeData>(
    '/api/uar/file-types',
    { interval: 0 }
  )

  if (loading && !data) {
    return <div className={styles.panel}><span className={styles.loading}>Loading...</span></div>
  }

  if (error) {
    // Read-only fallback — not critical
    return null
  }

  const allowed = data?.allowed_extensions ?? []
  const blocked = data?.blocked_extensions ?? []

  return (
    <div className={styles.panel}>
      <h4 className={styles.title}>File Type Controls</h4>
      <div className={styles.section}>
        <span className={styles.label}>Allowed:</span>
        <div className={styles.tags}>
          {allowed.map((ext) => (
            <span key={ext} className={styles.tag}>{ext}</span>
          ))}
          {allowed.length === 0 && (
            <span className={styles.note}>All extensions allowed (no whitelist)</span>
          )}
        </div>
      </div>
      <div className={styles.section}>
        <span className={styles.label}>Blocked:</span>
        <div className={styles.tags}>
          {blocked.map((ext) => (
            <span key={ext} className={`${styles.tag} ${styles.blocked}`}>{ext}</span>
          ))}
          {blocked.length === 0 && (
            <span className={styles.note}>No blocklist configured</span>
          )}
        </div>
      </div>
      <p className={styles.hint}>
        Configure via UAR_FILE_TYPE_WHITELIST and UAR_FILE_TYPE_BLOCKLIST env vars.
      </p>
    </div>
  )
}
