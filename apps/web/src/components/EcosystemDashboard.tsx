import { useState } from 'react'
import styles from './EcosystemDashboard.module.css'

interface Integration {
  name: string
  available: boolean
  status?: string
  url?: string
  version?: string
  error?: string
}

interface EcosystemData {
  integrations?: Integration[]
  status?: string
  error?: string
}

interface EcosystemDashboardProps {
  data: EcosystemData | null
  darkMode?: boolean
}

export function EcosystemDashboard({ data, darkMode = false }: EcosystemDashboardProps) {
  const [activeTab, setActiveTab] = useState<'status' | 'raw'>('status')

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the uor_ecosystem_status skill to check integrations.</p>
        </div>
      </div>
    )
  }

  if (data.error) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error}</p>
        </div>
      </div>
    )
  }

  const integrations = data.integrations || []
  const available = integrations.filter((i) => i.available)
  const unavailable = integrations.filter((i) => !i.available)

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          🌐 UOR Ecosystem ({available.length}/{integrations.length} online)
        </span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'status' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('status')}
          >
            Status
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
        </div>
      </div>

      {activeTab === 'status' ? (
        <div className={styles.scrollContent}>
          {integrations.length === 0 ? (
            <div className={styles.empty}>No integrations configured</div>
          ) : (
            <>
              <div className={styles.summaryBar}>
                <span className={`${styles.summaryItem} ${styles.pass}`}>
                  Online: <strong>{available.length}</strong>
                </span>
                <span className={`${styles.summaryItem} ${styles.fail}`}>
                  Offline: <strong>{unavailable.length}</strong>
                </span>
                <span className={styles.summaryItem}>
                  Total: <strong>{integrations.length}</strong>
                </span>
              </div>

              <div className={styles.integrationTable}>
                <div className={styles.intHeader}>
                  <span>Service</span>
                  <span>Status</span>
                  <span>Version</span>
                  <span>URL</span>
                </div>
                {integrations.map((int) => (
                  <div key={int.name} className={styles.intRow}>
                    <span className={styles.intName}>{int.name}</span>
                    <span className={`${styles.badge} ${int.available ? styles.badgeOnline : styles.badgeOffline}`}>
                      {int.available ? '● Online' : '● Offline'}
                    </span>
                    <span className={styles.intVer}>{int.version || '-'}</span>
                    <span className={styles.intUrl}>{int.url || '-'}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ) : (
        <div className={styles.rawPanel}>
          <pre className={styles.rawCode}>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
