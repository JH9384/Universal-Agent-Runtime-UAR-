import { useState, useCallback } from 'react'
import styles from './PhysicsVisualizer.module.css'

interface PhysicsData {
  success: boolean
  operation?: string
  physics_type?: string
  original_value?: string
  original_unit?: string
  converted_value?: string
  converted_unit?: string
  numerical_value?: number
  coordinate1?: string
  coordinate2?: string
  angular_distance?: string
  angular_distance_degrees?: number
  angular_distance_arcsec?: number
  from_frame?: string
  to_frame?: string
  original_ra?: string
  original_dec?: string
  transformed_ra?: string
  transformed_dec?: string
  wavelength?: string
  energy?: string
  energy_eV?: number
  redshift?: string
  luminosity_distance?: string
  luminosity_distance_Mpc?: number
  error?: string
}

interface PhysicsVisualizerProps {
  data: PhysicsData | null
  darkMode?: boolean
}

function ResultCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.resultCard}>
      <h4 className={styles.cardTitle}>{title}</h4>
      <div className={styles.cardContent}>{children}</div>
    </div>
  )
}

function ValueRow({ label, value }: { label: string; value: string | number | undefined }) {
  if (value === undefined || value === null) return null
  return (
    <div className={styles.valueRow}>
      <span className={styles.label}>{label}:</span>
      <span className={styles.value}>{String(value)}</span>
    </div>
  )
}

export function PhysicsVisualizer({ data, darkMode = false }: PhysicsVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'results' | 'raw'>('results')

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(() => {})
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the physics_compute skill to generate computation results.</p>
        </div>
      </div>
    )
  }

  if (!data.success) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>Physics Computation</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>{data.error || 'Computation failed'}</p>
        </div>
      </div>
    )
  }

  const op = data.operation || data.physics_type || 'compute'

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Physics Computation</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'results' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('results')}
          >
            Results
          </button>
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

      {activeTab === 'results' ? (
        <div className={styles.scrollContent}>
          {/* Unit Conversion */}
          {(data.original_value || data.converted_value) && (
            <ResultCard title="Unit Conversion">
              <ValueRow label="From" value={`${data.original_value} ${data.original_unit || ''}`} />
              <ValueRow label="To" value={`${data.converted_value} ${data.converted_unit || ''}`} />
              <ValueRow label="Numerical" value={data.numerical_value} />
            </ResultCard>
          )}

          {/* Coordinate Distance */}
          {(data.coordinate1 || data.angular_distance) && (
            <ResultCard title="Angular Distance">
              <ValueRow label="Coord 1" value={data.coordinate1} />
              <ValueRow label="Coord 2" value={data.coordinate2} />
              <ValueRow label="Distance" value={data.angular_distance} />
              <ValueRow label="Degrees" value={data.angular_distance_degrees?.toFixed(6)} />
              <ValueRow label="Arcseconds" value={data.angular_distance_arcsec?.toFixed(4)} />
            </ResultCard>
          )}

          {/* Coordinate Transform */}
          {(data.from_frame || data.transformed_ra) && (
            <ResultCard title="Coordinate Transform">
              <ValueRow label="From Frame" value={data.from_frame} />
              <ValueRow label="To Frame" value={data.to_frame} />
              <ValueRow label="Original RA/Dec" value={`${data.original_ra}, ${data.original_dec}`} />
              <ValueRow label="Transformed RA/Dec" value={`${data.transformed_ra}, ${data.transformed_dec}`} />
            </ResultCard>
          )}

          {/* Energy */}
          {(data.wavelength || data.energy) && (
            <ResultCard title="Photon Energy">
              <ValueRow label="Wavelength" value={data.wavelength} />
              <ValueRow label="Energy" value={data.energy} />
              <ValueRow label="Energy (eV)" value={data.energy_eV?.toExponential(4)} />
            </ResultCard>
          )}

          {/* Redshift / Cosmology */}
          {(data.redshift || data.luminosity_distance) && (
            <ResultCard title="Cosmology">
              <ValueRow label="Redshift (z)" value={data.redshift} />
              <ValueRow label="Luminosity Distance" value={data.luminosity_distance} />
              <ValueRow label="Distance (Mpc)" value={data.luminosity_distance_Mpc?.toFixed(4)} />
            </ResultCard>
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
