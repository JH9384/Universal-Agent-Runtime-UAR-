import { useState, useRef, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './KnowledgeGraph.module.css'

interface GraphNode {
  id: string
  type: string
  label: string
  category?: string
  status?: string
}

interface GraphEdge {
  source: string
  target: string
  type: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

const TYPE_COLORS: Record<string, string> = {
  run: '#3b82f6',
  goal: '#a855f7',
  recommendation: '#22c55e',
  outcome: '#f59e0b',
  incident: '#ef4444',
  alert: '#f97316',
  snapshot: '#06b6d4',
  operator: '#8b5cf6',
}

const TYPE_LABELS: Record<string, string> = {
  run: 'Run',
  goal: 'Goal',
  recommendation: 'Recommendation',
  outcome: 'Outcome',
  incident: 'Incident',
  alert: 'Alert',
  snapshot: 'Snapshot',
  operator: 'Operator',
}

export function KnowledgeGraphV2({
  centerId,
  centerType = 'run',
  onOpenReplay,
}: {
  centerId?: string
  centerType?: string
  onOpenReplay?: (runId: string) => void
}) {
  const [inputId, setInputId] = useState(centerId ?? '')
  const [inputType, setInputType] = useState(centerType)
  const [activeId, setActiveId] = useState(centerId ?? '')
  const [activeType, setActiveType] = useState(centerType)
  const [graphUrl, setGraphUrl] = useState('')
  const svgRef = useRef<SVGSVGElement>(null)
  const [svgSize, setSvgSize] = useState({ width: 600, height: 400 })

  const { data, loading, error } = useApiFetch<GraphData>(graphUrl)

  useEffect(() => {
    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect()
      setSvgSize({ width: rect.width || 600, height: rect.height || 400 })
    }
  }, [])

  const handleSearch = () => {
    if (inputId.trim()) {
      setActiveId(inputId.trim())
      setActiveType(inputType)
      setGraphUrl(`/api/uar/graph-v2/${encodeURIComponent(inputId.trim())}?center_type=${inputType}`)
    }
  }

  const nodes = data?.nodes ?? []
  const edges = data?.edges ?? []
  const positions = computePositions(nodes, edges, svgSize.width, svgSize.height)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Knowledge Graph v2</h4>
        <div className={styles.searchRow}>
          <select className={styles.select} aria-label="Center type" value={inputType} onChange={(e) => setInputType(e.target.value)}>
            <option value="run">Run</option>
            <option value="incident">Incident</option>
            <option value="recommendation">Recommendation</option>
          </select>
          <input className={styles.searchInput} placeholder="ID" value={inputId} onChange={(e) => setInputId(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} />
          <button className={styles.searchBtn} onClick={handleSearch}>Explore</button>
        </div>
      </div>

      {loading && <div className={styles.loading}>Building graph…</div>}
      {error && <div className={styles.error}>{error}</div>}

      {activeId && nodes.length > 0 && (
        <>
          <svg ref={svgRef} className={styles.graphSvg} viewBox={`0 0 ${svgSize.width} ${svgSize.height}`}>
            {edges.map((e, i) => {
              const s = positions[e.source]
              const t = positions[e.target]
              if (!s || !t) return null
              return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#cbd5e1" strokeWidth={1.5} />
            })}
            {nodes.map((n) => {
              const pos = positions[n.id]
              if (!pos) return null
              const color = TYPE_COLORS[n.type] || '#94a3b8'
              return (
                <g key={n.id} className={styles.nodeGroup} onClick={() => { if (n.type === 'run') onOpenReplay?.(n.id) }} style={{ cursor: n.type === 'run' ? 'pointer' : 'default' }}>
                  <circle cx={pos.x} cy={pos.y} r={n.type === 'run' ? 22 : 14} fill={color} opacity={0.9} />
                  <text x={pos.x} y={pos.y + 4} textAnchor="middle" fill="#fff" fontSize={n.type === 'run' ? 10 : 8} fontWeight={600}>
                    {n.label.length > 10 ? n.label.slice(0, 8) + '..' : n.label}
                  </text>
                </g>
              )
            })}
          </svg>
          <div className={styles.legend}>
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className={styles.legendItem}>
                <span className={styles.legendDot} style={{ background: color }} />
                {TYPE_LABELS[type]}
              </div>
            ))}
          </div>
        </>
      )}

      {activeId && nodes.length === 0 && !loading && (
        <div className={styles.emptyState}>No connections found for {activeId}.</div>
      )}
    </div>
  )
}

function computePositions(nodes: GraphNode[], edges: GraphEdge[], width: number, height: number): Record<string, { x: number; y: number }> {
  const pos: Record<string, { x: number; y: number }> = {}
  const cx = width / 2
  const cy = height / 2

  const center = nodes.find((n) => n.type === 'run' || n.type === 'incident' || n.type === 'recommendation')
  if (center) {
    pos[center.id] = { x: cx, y: cy }
  }

  const rings: Record<string, number> = { goal: 80, recommendation: 140, outcome: 200, incident: 180, alert: 220, snapshot: 260, operator: 240 }
  const byType: Record<string, GraphNode[]> = {}
  for (const n of nodes) {
    if (n.id === center?.id) continue
    if (!byType[n.type]) byType[n.type] = []
    byType[n.type].push(n)
  }

  for (const [type, ringNodes] of Object.entries(byType)) {
    const radius = rings[type] || 160
    const count = ringNodes.length
    ringNodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2
      pos[n.id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }
    })
  }

  return pos
}
