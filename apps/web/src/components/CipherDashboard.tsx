import { useState } from 'react'
import styles from './CipherDashboard.module.css'

interface CipherData {
  success?: boolean
  encrypted_data?: string
  decrypted_data?: string
  hash?: string
  signature?: string
  valid?: boolean
  algorithm?: string
  iv?: string
  error?: string
}

interface CipherDashboardProps {
  data: CipherData | null
  darkMode?: boolean
}

export function CipherDashboard({ data, darkMode = false }: CipherDashboardProps) {
  const [activeTab, setActiveTab] = useState<'result' | 'raw'>('result')

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the cipher_ops skill to generate cryptographic results.</p>
        </div>
      </div>
    )
  }

  if (data.success === false) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error || 'Operation failed'}</p>
        </div>
      </div>
    )
  }

  const algo = data.algorithm || 'Unknown'

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>🔐 {algo}</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'result' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('result')}
          >
            Result
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
        </div>
      </div>

      {activeTab === 'result' ? (
        <div className={styles.scrollContent}>
          {data.encrypted_data && (
            <div className={styles.resultCard}>
              <h4 className={styles.cardTitle}>Encrypted Data</h4>
              <code className={styles.hashBlock}>{data.encrypted_data}</code>
              {data.iv && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>IV:</span>
                  <code className={styles.metaValue}>{data.iv}</code>
                </div>
              )}
            </div>
          )}

          {data.decrypted_data && (
            <div className={styles.resultCard}>
              <h4 className={styles.cardTitle}>Decrypted Data</h4>
              <code className={styles.hashBlock}>{data.decrypted_data}</code>
            </div>
          )}

          {data.hash && (
            <div className={styles.resultCard}>
              <h4 className={styles.cardTitle}>Hash</h4>
              <code className={styles.hashBlock}>{data.hash}</code>
            </div>
          )}

          {data.signature && (
            <div className={styles.resultCard}>
              <h4 className={styles.cardTitle}>Signature</h4>
              <code className={styles.hashBlock}>{data.signature}</code>
            </div>
          )}

          {data.valid !== undefined && (
            <div className={styles.resultCard}>
              <h4 className={styles.cardTitle}>Verification</h4>
              <div className={`${styles.badge} ${data.valid ? styles.badgeSuccess : styles.badgeFail}`}>
                {data.valid ? '✓ Valid' : '✗ Invalid'}
              </div>
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
