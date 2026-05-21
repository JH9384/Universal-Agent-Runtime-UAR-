import { useState } from 'react'
import styles from './DocIngestDashboard.module.css'

interface Document {
  path: string
  extension: string
  size: number
  lines?: number
}

interface DocIngestData {
  files?: Document[]
  total_files?: number
  total_size?: number
  errors?: string[]
  status?: string
}

interface DocIngestDashboardProps {
  data: DocIngestData | null
  darkMode?: boolean
}

export function DocIngestDashboard({ data, darkMode = false }: DocIngestDashboardProps) {
  const [activeTab, setActiveTab] = useState<'files' | 'errors' | 'raw'>('files')

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the doc_ingest skill to process documents.</p>
        </div>
      </div>
    )
  }

  const files = data.files || []
  const errors = data.errors || []

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          📄 Documents ({data.total_files || files.length})
        </span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'files' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('files')}
          >
            Files
          </button>
          {errors.length > 0 && (
            <button
              className={`${styles.tabButton} ${activeTab === 'errors' ? styles.tabActive : ''}`}
              onClick={() => setActiveTab('errors')}
            >
              Errors ({errors.length})
            </button>
          )}
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
        </div>
      </div>

      {activeTab === 'files' && (
        <div className={styles.scrollContent}>
          <div className={styles.fileTable}>
            <div className={styles.fileHeader}>
              <span>Path</span>
              <span>Type</span>
              <span>Size</span>
              <span>Lines</span>
            </div>
            {files.map((doc, i) => (
              <div key={i} className={styles.fileRow}>
                <span className={styles.filePath} title={doc.path}>
                  {doc.path}
                </span>
                <span className={styles.fileExt}>{doc.extension}</span>
                <span className={styles.fileSize}>{formatBytes(doc.size)}</span>
                <span className={styles.fileLines}>{doc.lines ?? '-'}</span>
              </div>
            ))}
          </div>
          {data.total_size !== undefined && (
            <div className={styles.totalBar}>
              Total: {formatBytes(data.total_size)} across {data.total_files || files.length} files
            </div>
          )}
        </div>
      )}

      {activeTab === 'errors' && (
        <div className={styles.scrollContent}>
          {errors.map((err, i) => (
            <div key={i} className={styles.errorItem}>
              <span className={styles.errorIcon}>⚠️</span>
              <span className={styles.errorMsg}>{err}</span>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'raw' && (
        <div className={styles.rawPanel}>
          <pre className={styles.rawCode}>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}
