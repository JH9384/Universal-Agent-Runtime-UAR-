import { useState } from 'react'
import styles from './FpgaVisualizer.module.css'

interface Port {
  name: string
  direction: string
  width: number
}

interface WaveformCycle {
  cycle: number
  inputs: Record<string, number>
  outputs: Record<string, number>
}

interface Assertion {
  cycle: number
  signal: string
  expected: string
  actual: number
  status: string
}

interface FpgaData {
  module_name: string
  ports: Port[]
  test_vectors: number
  passed: number
  failed: number
  assertions: Assertion[]
  waveform: {
    signals: string[]
    cycles: number
    data: WaveformCycle[]
  }
}

interface FpgaVisualizerProps {
  data: FpgaData | null
  darkMode?: boolean
}

export function FpgaVisualizer({ data, darkMode = false }: FpgaVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'ports' | 'waveform' | 'results'>('ports')

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the fpga_verify skill to generate verification data.</p>
        </div>
      </div>
    )
  }

  const passRate = data.test_vectors > 0
    ? ((data.passed / (data.passed + data.failed)) * 100).toFixed(1)
    : '0'

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>{data.module_name}</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'ports' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('ports')}
          >
            Ports
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'waveform' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('waveform')}
          >
            Waveform
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'results' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('results')}
          >
            Results
          </button>
        </div>
      </div>

      <div className={styles.summaryBar}>
        <span className={styles.summaryItem}>
          Tests: <strong>{data.test_vectors}</strong>
        </span>
        <span className={`${styles.summaryItem} ${styles.pass}`}>
          Passed: <strong>{data.passed}</strong>
        </span>
        <span className={`${styles.summaryItem} ${data.failed > 0 ? styles.fail : ''}`}>
          Failed: <strong>{data.failed}</strong>
        </span>
        <span className={styles.summaryItem}>
          Rate: <strong>{passRate}%</strong>
        </span>
      </div>

      {activeTab === 'ports' && (
        <div className={styles.scrollContent}>
          <div className={styles.portTable}>
            <div className={styles.portHeader}>
              <span>Name</span>
              <span>Direction</span>
              <span>Width</span>
            </div>
            {data.ports.map((p) => (
              <div key={p.name} className={styles.portRow}>
                <span className={styles.portName}>{p.name}</span>
                <span className={styles[p.direction]}>{p.direction}</span>
                <span className={styles.portWidth}>{p.width}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'waveform' && (
        <div className={styles.scrollContent}>
          <div className={styles.waveTable}>
            <div className={styles.waveHeader}>
              <span>Cycle</span>
              {data.waveform.signals.map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            {data.waveform.data.map((cycle) => (
              <div key={cycle.cycle} className={styles.waveRow}>
                <span className={styles.waveCycle}>{cycle.cycle}</span>
                {data.waveform.signals.map((sig) => {
                  const val = cycle.inputs[sig] ?? cycle.outputs[sig] ?? 0
                  return (
                    <span key={sig} className={styles.waveValue}>
                      {val}
                    </span>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'results' && (
        <div className={styles.scrollContent}>
          {data.assertions.length === 0 ? (
            <div className={styles.allPass}>All tests passed</div>
          ) : (
            <div className={styles.assertTable}>
              <div className={styles.assertHeader}>
                <span>Cycle</span>
                <span>Signal</span>
                <span>Expected</span>
                <span>Actual</span>
                <span>Status</span>
              </div>
              {data.assertions.map((a, i) => (
                <div key={i} className={styles.assertRow}>
                  <span>{a.cycle}</span>
                  <span className={styles.assertSig}>{a.signal}</span>
                  <span>{a.expected}</span>
                  <span>{a.actual}</span>
                  <span className={styles.failBadge}>{a.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
