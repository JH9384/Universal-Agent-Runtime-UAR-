import { useState, useEffect } from 'react'
import styles from './UARPanel.module.css'

interface SkillHealth {
  name: string
  available: boolean
  last_error?: string
}

interface CircuitBreakerState {
  name: string
  state: 'closed' | 'open' | 'half_open'
  failures: number
  threshold: number
}

interface HealthData {
  skills: SkillHealth[]
  circuit_breakers: CircuitBreakerState[]
  recent_errors: string[]
  server_version: string
  uptime_seconds: number
}

export function HealthDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/health/dashboard')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setHealth(data)
      } catch (e) {
        setError(String(e))
      } finally {
        setLoading(false)
      }
    }
    fetchHealth()
    const id = setInterval(fetchHealth, 30000)
    return () => clearInterval(id)
  }, [])

  if (loading) return <div className={styles.healthLoading}>Loading health…</div>
  if (error) return <div className={styles.healthError}>Health check failed: {error}</div>
  if (!health) return null

  const availableCount = health.skills.filter(s => s.available).length
  const openBreakers = health.circuit_breakers.filter(b => b.state === 'open')

  return (
    <div className={styles.healthDashboard}>
      <h3 className={styles.healthTitle}>System Health</h3>

      <div className={styles.healthSummary}>
        <div className={styles.healthCard}>
          <span className={styles.healthValue}>{availableCount}</span>
          <span className={styles.healthLabel}>Skills Available</span>
        </div>
        <div className={styles.healthCard}>
          <span className={styles.healthValue}>{health.skills.length - availableCount}</span>
          <span className={styles.healthLabel}>Skills Unavailable</span>
        </div>
        <div className={styles.healthCard}>
          <span className={`${styles.healthValue} ${openBreakers.length > 0 ? styles.healthWarning : ''}`}>
            {openBreakers.length}
          </span>
          <span className={styles.healthLabel}>Open Circuit Breakers</span>
        </div>
      </div>

      {openBreakers.length > 0 && (
        <div className={styles.healthAlert}>
          <strong>⚠️ Open Circuit Breakers:</strong>
          <ul>
            {openBreakers.map(b => (
              <li key={b.name}>{b.name} ({b.failures}/{b.threshold} failures)</li>
            ))}
          </ul>
        </div>
      )}

      <h4 className={styles.healthSubtitle}>Skill Availability</h4>
      <div className={styles.healthGrid}>
        {health.skills.map(skill => (
          <div key={skill.name} className={`${styles.healthItem} ${skill.available ? styles.healthOk : styles.healthFail}`}>
            <span className={styles.healthDot}>{skill.available ? '●' : '○'}</span>
            <span className={styles.healthName}>{skill.name}</span>
            {!skill.available && skill.last_error && (
              <span className={styles.healthDetail}>{skill.last_error}</span>
            )}
          </div>
        ))}
      </div>

      {health.recent_errors.length > 0 && (
        <>
          <h4 className={styles.healthSubtitle}>Recent Errors</h4>
          <ul className={styles.healthErrors}>
            {health.recent_errors.map((err, i) => (
              <li key={i} className={styles.healthErrorItem}>{err}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
