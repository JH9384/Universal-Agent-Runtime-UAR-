import { useCallback, useState } from 'react'
import styles from './MathVisualizer.module.css'

interface MyHDLData {
  module_name?: string
  signals?: { name: string; type: string; width?: number; default?: number }[]
  verilog_stub?: string
  myhdl_available?: boolean
  note?: string
  error?: string
}

interface MyHDLVisualizerProps {
  data: MyHDLData | null
  darkMode?: boolean
}

export function MyHDLVisualizer({ data, darkMode = false }: MyHDLVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'signals' | 'verilog' | 'raw'>('signals')

  const handleCopy = useCallback(() => {
    if (!data?.verilog_stub) return
    navigator.clipboard.writeText(data.verilog_stub).catch(() => {})
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the myhdl_design skill to generate hardware module data.</p>
        </div>
      </div>
    )
  }

  if (data.error) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>MyHDL Design</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error}</p>
        </div>
      </div>
    )
  }

  const signals = data.signals || []

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>MyHDL — {data.module_name || 'module'}</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'signals' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('signals')}
          >
            Signals
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'verilog' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('verilog')}
          >
            Verilog
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
        </div>
      </div>

      {activeTab === 'signals' && (
        <div className={styles.scrollContent}>
          {signals.length === 0 ? (
            <p style={{ padding: '12px', fontSize: '13px' }}>No signals detected.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #444' }}>
                  <th style={{ textAlign: 'left', padding: '6px' }}>Name</th>
                  <th style={{ textAlign: 'left', padding: '6px' }}>Type</th>
                  <th style={{ textAlign: 'left', padding: '6px' }}>Width</th>
                  {signals.some((s) => s.default !== undefined) && (
                    <th style={{ textAlign: 'left', padding: '6px' }}>Default</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {signals.map((sig, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                    <td style={{ padding: '6px', fontFamily: 'monospace' }}>{sig.name}</td>
                    <td style={{ padding: '6px' }}>{sig.type}</td>
                    <td style={{ padding: '6px' }}>{sig.width ?? 1}</td>
                    {sig.default !== undefined && (
                      <td style={{ padding: '6px' }}>{sig.default}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {data.note && (
            <div
              style={{
                marginTop: '12px',
                padding: '10px',
                borderRadius: '6px',
                fontSize: '12px',
                background: data.myhdl_available ? '#d1fae5' : '#fef3c7',
                color: data.myhdl_available ? '#065f46' : '#92400e',
              }}
            >
              {data.note}
            </div>
          )}
        </div>
      )}

      {activeTab === 'verilog' && (
        <div className={styles.scrollContent}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
            <button className={styles.toolbarButton} onClick={handleCopy} title="Copy Verilog">
              Copy
            </button>
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: '12px',
              whiteSpace: 'pre-wrap',
              fontFamily: 'monospace',
              padding: '12px',
              background: darkMode ? '#1a1a1a' : '#f5f5f5',
              borderRadius: '6px',
            }}
          >
            {data.verilog_stub || 'No Verilog stub generated.'}
          </pre>
        </div>
      )}

      {activeTab === 'raw' && (
        <div className={styles.scrollContent}>
          <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
