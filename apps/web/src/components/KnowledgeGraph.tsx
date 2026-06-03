import { useState, useCallback, useRef, useEffect } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './KnowledgeGraph.module.css'

interface GraphNode {
  id: string
  type: 'run' | 'goal' | 'recommendation' | 'outcome' | 'incident'
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

interface KnowledgeGraphProps {
  runId?: string
  onOpenReplay?: (runId: string) => void
}

const TYPE_COLORS: Record<string, string> = {
  run: '#3b82f6',
  goal: '#a855f7',
  recommendation: '#22c55e',
  outcome: '#f59e0b',
  incident: '#ef4444',
}

const TYPE_LABELS: Record<string, string> = {
  run: 'Run',
  goal: 'Goal',
  recommendation: 'Recommendation',
  outcome: 'Outcome',
  incident: 'Incident',
}

export function KnowledgeGraph({ runId, onOpenReplay }: KnowledgeGraphProps) {
  const [inputRunId, setInputRunId] = useState(runId ?? '')
  const [activeRunId, setActiveRunId] = useState(runId ?? '')
  const svgRef = useRef<SVGSVGElement>(null)
  const [svgSize, setSvgSize] = useState({ width: 600, height: 400 })

  const [graphUrl, setGraphUrl] = useState<string>('')

  const handleSearch = useCallback(() => {
    if (inputRunId.trim()) {
      setActiveRunId(inputRunId.trim())
      setGraphUrl(`/api/uar/graph/${encodeURIComponent(inputRunId.trim())}`)
    }
  }, [inputRunId])

  const { data, loading, error } = useApiFetch<GraphData>(graphUrl)

  useEffect(() => {
    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect()
      setSvgSize({ width: rect.width || 600, height: rect.height || 400 })
    }
  }, [])

  const nodes = data?.nodes ?? []
  const edges = data?.edges ?? []

  // Simple force-directed layout (simulated)
  const positions = computePositions(nodes, edges, svgSize.width, svgSize.height)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4 className={styles.panelTitle}>Knowledge Graph</h4>
        <div className={styles.searchRow}>
          <input
            className={styles.searchInput}
            placeholder="Run ID"
            value={inputRunId}
            onChange={(e) => setInputRunId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button className={styles.searchBtn} onClick={handleSearch}>
            Explore
          </button>
        </div>
      </div>

      {loading && <div className={styles.loading}>Building graph…</div>}
      {error && <div className={styles.error}>{error}</div>}

      {activeRunId && nodes.length > 0 && (
        <>
          <svg
            ref={svgRef}
            className={styles.graphSvg}
            viewBox={`0 0 ${svgSize.width} ${svgSize.height}`}
          >
            {/* Edges */}
            {edges.map((e, i) => {
              const s = positions[e.source]
              const t = positions[e.target]
              if (!s || !t) return null
              return (
                <line
                  key={i}
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke="#cbd5e1"
                  strokeWidth={1.5}
                />
              )
            })}
            {/* Nodes */}
            {nodes.map((n) => {
              const pos = positions[n.id]
              if (!pos) return null
              const color = TYPE_COLORS[n.type] || '#94a3b8'
              return (
                <g
                  key={n.id}
                  className={styles.nodeGroup}
                  onClick={() => {
                    if (n.type === 'run') onOpenReplay?.(n.id)
                  }}
                  style={{ cursor: n.type === 'run' ? 'pointer' : 'default' }}
                >
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={n.type === 'run' ? 22 : 14}
                    fill={color}
                    opacity={0.9}
                  />
                  <text
                    x={pos.x}
                    y={pos.y + 4}
                    textAnchor="middle"
                    fill="#fff"
                    fontSize={n.type === 'run' ? 10 : 8}
                    fontWeight={600}
                  >
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

      {activeRunId && nodes.length === 0 && !loading && (
        <div className={styles.emptyState}>
          No connections found for {activeRunId}.
        </div>
      )}
    </div>
  )
}

function computePositions(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number
): Record<string, { x: number; y: number }> {
  const pos: Record<string, { x: number; y: number }> = {}
  const cx = width / 2
  const cy = height / 2

  // Center the run node
  const runNode = nodes.find((n) => n.type === 'run')
  if (runNode) {
    pos[runNode.id] = { x: cx, y: cy }
  }

  // Place other nodes in rings by type
  const rings: Record<string, number> = {
    goal: 80,
    recommendation: 140,
    outcome: 200,
    incident: 200,
  }

  const byType: Record<string, GraphNode[]> = {}
  for (const n of nodes) {
    if (n.type === 'run') continue
    if (!byType[n.type]) byType[n.type] = []
    byType[n.type].push(n)
  }

  for (const [type, ringNodes] of Object.entries(byType)) {
    const radius = rings[type] || 160
    const count = ringNodes.length
    ringNodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2
      pos[n.id] = {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      }
    })
  }

  return pos
}
