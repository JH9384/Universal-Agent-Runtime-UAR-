import { useState, useEffect, useCallback } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './FleetHealthWidget.module.css'

interface FleetNode {
  node_id: string
  node_name: string
  version: string
  health_score: number
  cert_level: string
  active_runs: number
  skills_available: number
  status: string
  seconds_since_report: number
}

interface FleetHealthData {
  fleet_health_score: number | null
  nodes_online: number
  nodes_total: number
  critical_nodes: FleetNode[]
  cert_distribution: Record<string, number>
}

interface FleetFailureData {
  hotspots: Array<{
    skill: string
    affected_nodes: number
    total_failures: number
    nodes: Array<{ node_id: string; count: number; error: string }>
  }>
  correlated_skills: string[]
  nodes_reporting: number
}

export function FleetHealthWidget() {
  const [healthData, setHealthData] = useState<FleetHealthData | null>(null)
  const [failureData, setFailureData] = useState<FleetFailureData | null>(null)
  const [nodesData, setNodesData] = useState<FleetNode[]>([])

  const { data: hData } = useApiFetch('/api/uar/fleet/health')
  const { data: fData } = useApiFetch('/api/uar/fleet/failures')
  const { data: nData } = useApiFetch('/api/uar/fleet/nodes')

  useEffect(() => {
    if (hData) setHealthData(hData as FleetHealthData)
  }, [hData])

  useEffect(() => {
    if (fData) setFailureData(fData as FleetFailureData)
  }, [fData])

  useEffect(() => {
    if (nData && (nData as any).nodes) {
      setNodesData((nData as any).nodes as FleetNode[])
    }
  }, [nData])

  const _statusClass = useCallback((status: string) => {
    if (status === 'online') return styles.statusOnline
    if (status === 'stale') return styles.statusStale
    return styles.statusOffline
  }, [])

  const _certClass = useCallback((level: string) => {
    if (level === 'Gold') return styles.certGold
    if (level === 'Silver') return styles.certSilver
    return styles.certExperimental
  }, [])

  return (
    <div className={styles.widget} role="region" aria-label="Fleet Health Dashboard">
      <div className={styles.header}>
        <h2 className={styles.title}>Fleet Dashboard</h2>
        {healthData && (
          <div className={styles.summary}>
            <span className={styles.score}>
              {healthData.fleet_health_score !== null
                ? `Fleet Health: ${healthData.fleet_health_score}`
                : 'No fleet data'}
            </span>
            <span className={styles.count}>
              {healthData.nodes_online}/{healthData.nodes_total} nodes online
            </span>
          </div>
        )}
      </div>

      {healthData && healthData.critical_nodes.length > 0 && (
        <div className={styles.criticalBanner} role="alert">
          <strong>Critical Nodes:</strong>{' '}
          {healthData.critical_nodes.map((n) => n.node_name).join(', ')}
        </div>
      )}

      {failureData && failureData.hotspots.length > 0 && (
        <div className={styles.hotspotBanner} role="alert">
          <strong>Fleet-Wide Hotspots:</strong>{' '}
          {failureData.hotspots.map((h) => `${h.skill} (${h.affected_nodes} nodes)`).join(', ')}
        </div>
      )}

      <div className={styles.grid}>
        {nodesData.map((node) => (
          <div
            key={node.node_id}
            className={`${styles.card} ${_statusClass(node.status)}`}
          >
            <div className={styles.cardHeader}>
              <span className={styles.nodeName}>{node.node_name}</span>
              <span className={`${styles.badge} ${_certClass(node.cert_level)}`}>
                {node.cert_level}
              </span>
            </div>
            <div className={styles.cardBody}>
              <div className={styles.metric}>
                <span className={styles.metricLabel}>Health</span>
                <span className={styles.metricValue}>{node.health_score}</span>
              </div>
              <div className={styles.metric}>
                <span className={styles.metricLabel}>Active Runs</span>
                <span className={styles.metricValue}>{node.active_runs}</span>
              </div>
              <div className={styles.metric}>
                <span className={styles.metricLabel}>Skills</span>
                <span className={styles.metricValue}>{node.skills_available}</span>
              </div>
            </div>
            <div className={styles.cardFooter}>
              <span className={styles.version}>v{node.version}</span>
              <span className={styles.status}>{node.status}</span>
            </div>
          </div>
        ))}
      </div>

      {nodesData.length === 0 && (
        <div className={styles.empty}>No fleet nodes registered yet.</div>
      )}
    </div>
  )
}
