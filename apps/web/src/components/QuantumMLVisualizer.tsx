import { useCallback, useState } from 'react'
import styles from './MathVisualizer.module.css'

interface QuantumMLData {
  status: string
  task?: string
  qubits?: number
  layers?: number
  steps?: number
  mse?: number
  accuracy?: number
  predictions?: number[]
  targets?: number[]
  probabilities?: number[]
  hamiltonian?: string
  ground_state_energy?: number
  expectation_value?: number
  molecule?: string
  basis?: string
  charge?: number
  mock_energy?: number | null
  note?: string
  error?: string
}

interface QuantumMLVisualizerProps {
  data: QuantumMLData | null
  darkMode?: boolean
}

export function QuantumMLVisualizer({ data, darkMode = false }: QuantumMLVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'predictions' | 'raw'>('overview')

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(() => {})
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the quantum_ml skill to generate results.</p>
        </div>
      </div>
    )
  }

  if (data.error || data.status === 'failed') {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>Quantum ML</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error || 'Quantum ML computation failed'}</p>
        </div>
      </div>
    )
  }

  const task = data.task || 'unknown'
  const isQNN = task === 'qnn_regression' || task === 'qnn_classification'
  const isVQE = task === 'vqe'
  const isQAOA = task === 'qaoa'
  const isQChem = task === 'qchem_molecule'

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Quantum ML — {task}</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'overview' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          {isQNN && (
            <button
              className={`${styles.tabButton} ${activeTab === 'predictions' ? styles.tabActive : ''}`}
              onClick={() => setActiveTab('predictions')}
            >
              Results
            </button>
          )}
          <button
            className={`${styles.tabButton} ${activeTab === 'raw' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('raw')}
          >
            Raw
          </button>
          <button className={styles.toolbarButton} onClick={handleCopy} title="Copy JSON">
            📋
          </button>
        </div>
      </div>

      {activeTab === 'overview' && (
        <div className={styles.scrollContent}>
          <div className={styles.infoGrid} style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '16px' }}>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{data.qubits ?? '-'}</div>
              <div className={styles.infoLabel}>Qubits</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{data.layers ?? '-'}</div>
              <div className={styles.infoLabel}>Layers</div>
            </div>
            <div className={styles.infoCard}>
              <div className={styles.infoValue}>{data.steps ?? '-'}</div>
              <div className={styles.infoLabel}>Steps</div>
            </div>
            {isQNN && data.mse !== undefined && (
              <div className={styles.infoCard}>
                <div className={styles.infoValue}>{data.mse.toFixed(4)}</div>
                <div className={styles.infoLabel}>MSE</div>
              </div>
            )}
            {isQNN && data.accuracy !== undefined && (
              <div className={styles.infoCard}>
                <div className={styles.infoValue}>{(data.accuracy * 100).toFixed(1)}%</div>
                <div className={styles.infoLabel}>Accuracy</div>
              </div>
            )}
            {isVQE && data.ground_state_energy !== undefined && (
              <div className={styles.infoCard}>
                <div className={styles.infoValue}>{data.ground_state_energy.toFixed(4)}</div>
                <div className={styles.infoLabel}>Ground State Energy</div>
              </div>
            )}
            {isQAOA && data.expectation_value !== undefined && (
              <div className={styles.infoCard}>
                <div className={styles.infoValue}>{data.expectation_value.toFixed(4)}</div>
                <div className={styles.infoLabel}>Expectation</div>
              </div>
            )}
            {isQChem && data.mock_energy !== undefined && (
              <div className={styles.infoCard}>
                <div className={styles.infoValue}>{data.mock_energy?.toFixed(4) ?? '-'}</div>
                <div className={styles.infoLabel}>Energy (Ha)</div>
              </div>
            )}
          </div>

          {data.note && (
            <div style={{ padding: '12px', background: '#fef3c7', borderRadius: '6px', fontSize: '13px' }}>
              {data.note}
            </div>
          )}
        </div>
      )}

      {activeTab === 'predictions' && isQNN && (
        <div className={styles.scrollContent}>
          {data.targets && data.predictions && (
            <div>
              <h4 className={styles.sectionTitle}>Predictions vs Targets</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #444' }}>
                    <th style={{ textAlign: 'left', padding: '4px' }}>Index</th>
                    <th style={{ textAlign: 'left', padding: '4px' }}>Target</th>
                    <th style={{ textAlign: 'left', padding: '4px' }}>Prediction</th>
                    {data.probabilities && <th style={{ textAlign: 'left', padding: '4px' }}>Probability</th>}
                  </tr>
                </thead>
                <tbody>
                  {data.targets.map((t: number, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                      <td style={{ padding: '4px' }}>{i}</td>
                      <td style={{ padding: '4px' }}><code>{Number(t).toFixed(4)}</code></td>
                      <td style={{ padding: '4px' }}><code>{Number(data.predictions![i]).toFixed(4)}</code></td>
                      {data.probabilities && (
                        <td style={{ padding: '4px' }}><code>{Number(data.probabilities[i]).toFixed(4)}</code></td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
