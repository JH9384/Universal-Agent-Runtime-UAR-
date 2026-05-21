import { useState } from 'react'
import styles from './AutonomiDashboard.module.css'

interface AutonomiData {
  status: string
  available: boolean
  package_version?: string
  network?: string
  has_wallet?: boolean
  wallet_address?: string
  wallet_error?: string
  error?: string
}

interface AutonomiDashboardProps {
  data: AutonomiData | null
  darkMode?: boolean
}

export function AutonomiDashboard({ data, darkMode = false }: AutonomiDashboardProps) {
  const [activeTab, setActiveTab] = useState<'status' | 'raw'>('status')

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the autonomi_status skill to check connectivity.</p>
        </div>
      </div>
    )
  }

  if (data.status === 'failed') {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Unavailable</div>
          <p className={styles.errorText}>{data.error || 'Autonomi package not installed'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          ☁️ Autonomi ({data.network || 'unknown'})
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
          <div className={styles.statusGrid}>
            <div className={styles.statusCard}>
              <span className={styles.cardLabel}>Package</span>
              <span className={`${styles.badge} ${data.available ? styles.badgeOk : styles.badgeFail}`}>
                {data.available ? 'Installed' : 'Missing'}
              </span>
            </div>

            <div className={styles.statusCard}>
              <span className={styles.cardLabel}>Version</span>
              <span className={styles.cardValue}>{data.package_version || 'unknown'}</span>
            </div>

            <div className={styles.statusCard}>
              <span className={styles.cardLabel}>Network</span>
              <span className={styles.cardValue}>{data.network || 'unknown'}</span>
            </div>

            <div className={styles.statusCard}>
              <span className={styles.cardLabel}>Wallet</span>
              <span className={`${styles.badge} ${data.has_wallet ? styles.badgeOk : styles.badgeWarn}`}>
                {data.has_wallet ? 'Configured' : 'Not Set'}
              </span>
            </div>
          </div>

          {data.wallet_address && (
            <div className={styles.walletCard}>
              <span className={styles.walletLabel}>Wallet Address</span>
              <code className={styles.walletAddr}>{data.wallet_address}</code>
            </div>
          )}

          {data.wallet_error && (
            <div className={styles.walletError}>
              <span className={styles.walletLabel}>Wallet Error</span>
              <span className={styles.errorText}>{data.wallet_error}</span>
            </div>
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
