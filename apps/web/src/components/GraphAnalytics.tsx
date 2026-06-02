import { useState } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './GraphAnalytics.module.css'

interface AnalyticsData {
  center_id: string
  center_type: string
  generated_at: number
  node_count: number
  edge_count: number
  most_connected: { id: string; degree: number }[]
  outcome_paths: { run: string; recommendation: string; outcome: string }[]
  trust_clusters: Record<string, number>
  resolution_routes: Record<string, Record<string, number>>
}

export function GraphAnalytics({
  centerId,
  centerType = 'run',
}: {
  centerId?: string
  centerType?: string
}) {
  const [inputId, setInputId] = useState(centerId ?? '')
  const [inputType, setInputType] = useState(centerType)
  const [activeId, setActiveId] = useState(centerId ?? '')
  const [activeType, setActiveType] = useState(centerType)
  const [url, setUrl] = useState('')

  const { data, loading, error } = useApiFetch<AnalyticsData>(url)

  const handleSearch = () => {
    if (inputId.trim()) {
      setActiveId(inputId.trim())
      setActiveType(inputType)
      setUrl(`/api/uar/graph-analytics/${inputId.trim()}?center_type=${inputType}`)
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Graph Analytics</h4>
        <div className={styles.searchRow}>
          <select className={styles.select} aria-label="Center type" value={inputType} onChange={(e) => setInputType(e.target.value)}>
            <option value="run">Run</option>
            <option value="incident">Incident</option>
            <option value="recommendation">Recommendation</option>
          </select>
          <input className={styles.searchInput} placeholder="ID" value={inputId} onChange={(e) => setInputId(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} />
          <button className={styles.searchBtn} onClick={handleSearch}>Analyze</button>
        </div>
      </div>

      {loading && <div className={styles.loading}>Analyzing…</div>}
      {error && <div className={styles.error}>{error}</div>}

      {data && (
        <>
          <div className={styles.overview}>
            <StatBox label="Nodes" value={data.node_count} />
            <StatBox label="Edges" value={data.edge_count} />
            <StatBox label="Paths" value={data.outcome_paths.length} />
          </div>

          {data.most_connected.length > 0 && (
            <>
              <h5 className={styles.sectionTitle}>Most Connected</h5>
              {data.most_connected.map((n) => (
                <div key={n.id} className={styles.connectedRow}>
                  <span className={styles.connectedId}>{n.id}</span>
                  <span className={styles.connectedDegree}>{n.degree} connections</span>
                </div>
              ))}
            </>
          )}

          {Object.keys(data.trust_clusters).length > 0 && (
            <>
              <h5 className={styles.sectionTitle}>Trust Clusters</h5>
              {(() => {
                const maxCluster = Math.max(1, ...Object.values(data.trust_clusters))
                return Object.entries(data.trust_clusters).map(([band, count]) => (
                  <div key={band} className={styles.clusterRow}>
                    <span className={styles.clusterLabel}>{band.replaceAll('_', ' ')}</span>
                    <div className={styles.clusterBarWrap}>
                      <div className={styles.clusterBar} style={{ width: `${Math.round((count / maxCluster) * 100)}%` }} />
                    </div>
                    <span className={styles.clusterCount}>{count}</span>
                  </div>
                ))
              })()}
            </>
          )}

          {data.outcome_paths.length > 0 && (
            <>
              <h5 className={styles.sectionTitle}>Outcome Paths</h5>
              {data.outcome_paths.map((p) => (
                <div key={`${p.recommendation}→${p.outcome}`} className={styles.pathRow}>
                  <span className={styles.pathRec}>{p.recommendation}</span>
                  <span className={styles.pathArrow}>→</span>
                  <span className={styles.pathOutcome}>{p.outcome}</span>
                </div>
              ))}
            </>
          )}

          {Object.keys(data.resolution_routes).length > 0 && (
            <>
              <h5 className={styles.sectionTitle}>Resolution Routes</h5>
              {Object.entries(data.resolution_routes).map(([cat, outcomes]) => (
                <div key={cat} className={styles.routeBlock}>
                  <div className={styles.routeCat}>{cat}</div>
                  {Object.entries(outcomes).map(([otype, count]) => (
                    <div key={otype} className={styles.routeRow}>
                      <span>{otype}</span>
                      <span className={styles.routeCount}>{count}</span>
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}
        </>
      )}

      {activeId && !data && !loading && (
        <div className={styles.emptyState}>No analytics available for {activeId}.</div>
      )}
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.statBox}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}
