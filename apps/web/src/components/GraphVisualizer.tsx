import { useState, useCallback, useMemo, useRef, useEffect, type MouseEvent } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Panel,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import styles from './GraphVisualizer.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GraphNode {
  id: string
  label?: string
  skill?: string
  type?: string
  [key: string]: unknown
}

export interface GraphEdge {
  from?: string
  to?: string
  type?: string
  label?: string
  [key: string]: unknown
}

export interface GraphData {
  nodes?: GraphNode[]
  edges?: GraphEdge[]
}

// ---------------------------------------------------------------------------
// Layout engine — simple force-directed + tree-aware hybrid
// ---------------------------------------------------------------------------

interface LayoutNode {
  id: string
  x: number
  y: number
  vx: number
  vy: number
  mass: number
}

function computeLayout(
  rawNodes: GraphNode[],
  rawEdges: GraphEdge[],
  width: number,
  height: number
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, LayoutNode>()
  const n = rawNodes.length
  if (n === 0) return new Map()

  // Initialize in a circle so force-directed has good starting points
  const cx = width / 2
  const cy = height / 2
  const radius = Math.min(width, height) * 0.35
  rawNodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(n, 1)
    positions.set(node.id || String(i), {
      id: node.id || String(i),
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      vx: 0,
      vy: 0,
      mass: 1 + (rawEdges.filter((e) => e.from === node.id || e.to === node.id).length * 0.3),
    })
  })

  // Force-directed iterations
  const iterations = 120
  const repulsion = 8000
  const attraction = 0.008
  const damping = 0.85
  const minDist = 80

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations

    // Repulsion (node vs node)
    const nodeList = Array.from(positions.values())
    for (let i = 0; i < nodeList.length; i++) {
      for (let j = i + 1; j < nodeList.length; j++) {
        const a = nodeList[i]
        const b = nodeList[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.sqrt(dx * dx + dy * dy) || 1
        if (dist < minDist) dist = minDist
        const force = (repulsion * temp) / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        a.vx += fx / a.mass
        a.vy += fy / a.mass
        b.vx -= fx / b.mass
        b.vy -= fy / b.mass
      }
    }

    // Attraction (edges pull nodes together)
    for (const e of rawEdges) {
      const a = positions.get(e.from || '')
      const b = positions.get(e.to || '')
      if (!a || !b) continue
      let dx = b.x - a.x
      let dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const targetLen = 140
      const force = (dist - targetLen) * attraction * temp
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      a.vx += fx / a.mass
      a.vy += fy / a.mass
      b.vx -= fx / b.mass
      b.vy -= fy / b.mass
    }

    // Center gravity
    for (const node of nodeList) {
      node.vx += (cx - node.x) * 0.001 * temp
      node.vy += (cy - node.y) * 0.001 * temp
    }

    // Apply velocity with damping
    for (const node of nodeList) {
      node.vx *= damping
      node.vy *= damping
      node.x += node.vx
      node.y += node.vy
    }
  }

  const result = new Map<string, { x: number; y: number }>()
  for (const [id, node] of positions) {
    result.set(id, { x: node.x, y: node.y })
  }
  return result
}

function getCommunities(nodes: GraphNode[], edges: GraphEdge[]): string[][] {
  const adjacency = new Map<string, Set<string>>()
  nodes.forEach((node, index) => {
    adjacency.set(node.id || String(index), new Set())
  })
  edges.forEach((edge) => {
    if (!edge.from || !edge.to) return
    if (!adjacency.has(edge.from) || !adjacency.has(edge.to)) return
    adjacency.get(edge.from)?.add(edge.to)
    adjacency.get(edge.to)?.add(edge.from)
  })

  const visited = new Set<string>()
  const communities: string[][] = []
  adjacency.forEach((_neighbors, start) => {
    if (visited.has(start)) return
    const queue = [start]
    const community: string[] = []
    visited.add(start)
    while (queue.length > 0) {
      const current = queue.shift()!
      community.push(current)
      adjacency.get(current)?.forEach((next) => {
        if (!visited.has(next)) {
          visited.add(next)
          queue.push(next)
        }
      })
    }
    communities.push(community)
  })
  return communities.sort((a, b) => b.length - a.length)
}

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------

const typeIcons: Record<string, string> = {
  skill: '⚡',
  file: '📄',
  module: '📦',
  function: '🔧',
  entity: '🎯',
  class: '🏗️',
  recipe: '🍳',
  ecosystem: '🌐',
  default: '●',
}

const typeColors: Record<string, string> = {
  skill: '#3b82f6',
  file: '#10b981',
  module: '#f59e0b',
  function: '#8b5cf6',
  entity: '#ec4899',
  class: '#06b6d4',
  recipe: '#f97316',
  ecosystem: '#22c55e',
  default: '#6b7280',
}

const typeClasses: Record<string, string> = {
  skill: styles.typeSkill,
  file: styles.typeFile,
  module: styles.typeModule,
  function: styles.typeFunction,
  entity: styles.typeEntity,
  class: styles.typeClass,
  recipe: styles.typeRecipe,
  ecosystem: styles.typeEcosystem,
  default: styles.typeDefault,
}

function getTypeClass(type: string): string {
  return typeClasses[type] || typeClasses.default
}

function CustomNode({ data, selected }: NodeProps) {
  const type = (data.type as string) || 'default'
  const icon = typeIcons[type] || typeIcons.default
  return (
    <div
      className={`${styles.customNode} ${getTypeClass(type)} ${
        selected ? styles.selectedNode : ''
      }`}
      title={data.label as string}
    >
      <Handle type="target" position={Position.Top} className={styles.nodeHandle} />
      <span className={styles.nodeIcon}>{icon}</span>
      <span className={styles.nodeLabel}>{data.label as string}</span>
      <Handle type="source" position={Position.Bottom} className={styles.nodeHandle} />
    </div>
  )
}

const nodeTypes = { custom: CustomNode }

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface GraphVisualizerProps {
  graph: GraphData | null
  darkMode?: boolean
  onExport?: (format: 'json' | 'mermaid' | 'png') => void
}

export function GraphVisualizer({ graph, darkMode = false, onExport }: GraphVisualizerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [layoutSeed, setLayoutSeed] = useState(0)

  // Build typed nodes/edges from raw graph data
  const { rawNodes, rawEdges, allTypes } = useMemo(() => {
    if (!graph) return { rawNodes: [] as GraphNode[], rawEdges: [] as GraphEdge[], allTypes: new Set<string>() }
    const nodes = graph.nodes || []
    const edges = graph.edges || []
    const types = new Set<string>()
    nodes.forEach((n) => {
      if (n.type) types.add(n.type as string)
    })
    return { rawNodes: nodes, rawEdges: edges, allTypes: types }
  }, [graph])

  // Layout
  const layoutPositions = useMemo(() => {
    if (!graph || rawNodes.length === 0) return new Map<string, { x: number; y: number }>()
    const container = containerRef.current
    const width = container?.clientWidth || 800
    const height = container?.clientHeight || 600
    return computeLayout(rawNodes, rawEdges, width, height)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, layoutSeed])

  // Filter nodes
  const visibleNodeIds = useMemo(() => {
    const ids = new Set<string>()
    rawNodes.forEach((n, i) => {
      const id = n.id || String(i)
      const type = (n.type as string) || 'default'
      const label = String(n.label || n.skill || n.id || '').toLowerCase()
      const matchesType = filterType === 'all' || type === filterType
      const matchesSearch = !searchQuery || label.includes(searchQuery.toLowerCase())
      if (matchesType && matchesSearch) ids.add(id)
    })
    return ids
  }, [rawNodes, filterType, searchQuery])

  const graphStats = useMemo(() => {
    const visibleNodes = rawNodes.filter((node, index) =>
      visibleNodeIds.has(node.id || String(index))
    )
    const visibleIds = new Set(
      visibleNodes.map((node, index) => node.id || String(index))
    )
    const visibleEdges = rawEdges.filter(
      (edge) =>
        edge.from &&
        edge.to &&
        visibleIds.has(edge.from) &&
        visibleIds.has(edge.to)
    )
    const degree = new Map<string, number>()
    visibleNodes.forEach((node, index) => {
      degree.set(node.id || String(index), 0)
    })
    visibleEdges.forEach((edge) => {
      if (!edge.from || !edge.to) return
      degree.set(edge.from, (degree.get(edge.from) || 0) + 1)
      degree.set(edge.to, (degree.get(edge.to) || 0) + 1)
    })
    const hub = Array.from(degree.entries()).sort((a, b) => b[1] - a[1])[0]
    const communities = getCommunities(visibleNodes, visibleEdges)
    const maxEdges = Math.max(visibleNodes.length * (visibleNodes.length - 1), 1)
    return {
      visibleNodeCount: visibleNodes.length,
      visibleEdgeCount: visibleEdges.length,
      communityCount: communities.length,
      largestCommunity: communities[0]?.length || 0,
      density: visibleEdges.length / maxEdges,
      hub,
    }
  }, [rawNodes, rawEdges, visibleNodeIds])

  // Build ReactFlow nodes/edges
  const initialNodes: Node[] = useMemo(() => {
    const nodeIndex = new Map<string, string>()
    const result = rawNodes.map((n, i) => {
      const rawId = n.id || String(i)
      const nodeId = String(i)
      nodeIndex.set(rawId, nodeId)
      const pos = layoutPositions.get(rawId) || { x: (i % 5) * 180, y: Math.floor(i / 5) * 120 }
      const type = (n.type as string) || 'default'
      return {
        id: nodeId,
        type: 'custom',
        position: pos,
        data: {
          label: n.label || n.skill || String(rawId).split('/').pop() || rawId,
          type,
          originalId: rawId,
          ...n,
        },
        hidden: !visibleNodeIds.has(rawId),
      }
    })
    return result
  }, [rawNodes, layoutPositions, visibleNodeIds])

  const initialEdges: Edge[] = useMemo(() => {
    const nodeIndex = new Map<string, string>()
    rawNodes.forEach((n, i) => {
      nodeIndex.set(n.id || String(i), String(i))
    })
    return rawEdges
      .map((e, i) => {
        const source = e.from ? nodeIndex.get(e.from) : undefined
        const target = e.to ? nodeIndex.get(e.to) : undefined
        if (source === undefined || target === undefined) return null
        const srcVisible = visibleNodeIds.has(e.from || '')
        const tgtVisible = visibleNodeIds.has(e.to || '')
        return {
          id: `e-${i}`,
          source,
          target,
          label: e.label || e.type || '',
          animated: true,
          hidden: !srcVisible || !tgtVisible,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
          style: { stroke: '#94a3b8', strokeWidth: 2 },
          labelStyle: { fill: darkMode ? '#94a3b8' : '#4b5563', fontSize: 11 },
          labelBgStyle: { fill: darkMode ? '#1f2937' : '#ffffff', fillOpacity: 0.9 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
        }
      })
      .filter(Boolean) as Edge[]
  }, [rawEdges, rawNodes, visibleNodeIds, darkMode])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialNodes, initialEdges])

  const onNodeClick = useCallback((_event: MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const handleExport = useCallback(
    (format: 'json' | 'mermaid' | 'png') => {
      if (format === 'json') {
        const blob = new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'graph.json'
        a.click()
        URL.revokeObjectURL(url)
      } else if (format === 'mermaid') {
        const nodeMap = new Map<string, string>()
        rawNodes.forEach((n, i) => {
          const safeId = `n${i}`
          nodeMap.set(n.id || String(i), safeId)
        })
        let mermaid = 'graph TD\n'
        rawEdges.forEach((e) => {
          const fromId = nodeMap.get(e.from || '')
          const toId = nodeMap.get(e.to || '')
          if (fromId && toId) {
            mermaid += `  ${fromId} -->|${e.type || ''}| ${toId}\n`
          }
        })
        const blob = new Blob([mermaid], { type: 'text/plain' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'graph.mmd'
        a.click()
        URL.revokeObjectURL(url)
      }
      onExport?.(format)
    },
    [graph, rawNodes, rawEdges, onExport]
  )

  if (!graph || (rawNodes.length === 0 && rawEdges.length === 0)) {
    return (
      <div className={`${styles.emptyState} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.emptyIcon}>📊</div>
        <p>No graph data available.</p>
        <p className={styles.emptyHint}>
          Run <code>dependency_map</code> or <code>graphrag_index</code> to generate a graph.
        </p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={`${styles.graphContainer} ${darkMode ? styles.dark : ''}`}
    >
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <input
          type="text"
          placeholder="Search nodes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={styles.searchInput}
        />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className={styles.filterSelect}
          title="Filter by node type"
        >
          <option value="all">All types</option>
          {Array.from(allTypes).sort().map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button
          className={styles.toolbarButton}
          onClick={() => setLayoutSeed((s) => s + 1)}
          title="Re-run layout"
        >
          🔄 Layout
        </button>
        <div className={styles.exportGroup}>
          <button className={styles.toolbarButton} onClick={() => handleExport('json')} title="Export JSON">
            JSON
          </button>
          <button className={styles.toolbarButton} onClick={() => handleExport('mermaid')} title="Export Mermaid">
            Mermaid
          </button>
        </div>
      </div>

      {/* ReactFlow canvas */}
      <div className={styles.flowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
          attributionPosition="bottom-right"
        >
          <Background color={darkMode ? '#374151' : '#e5e7eb'} gap={16} size={1} />
          <Controls className={styles.controls} />
          <MiniMap
            nodeStrokeColor={(n) => typeColors[n.data?.type as string] || typeColors.default}
            nodeColor={(n) => typeColors[n.data?.type as string] || typeColors.default}
            className={styles.minimap}
          />
        </ReactFlow>
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div className={`${styles.detailPanel} ${darkMode ? styles.darkPanel : ''}`}>
          <div className={styles.detailHeader}>
            <strong>Node Details</strong>
            <button className={styles.closeBtn} onClick={() => setSelectedNode(null)}>
              ✕
            </button>
          </div>
          <div className={styles.detailBody}>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Label</span>
              <span className={styles.detailValue}>{String(selectedNode.data?.label || '')}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Type</span>
              <span
                className={`${styles.detailBadge} ${getTypeClass(
                  (selectedNode.data?.type as string) || 'default'
                )}`}
              >
                {String(selectedNode.data?.type || 'default')}
              </span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>ID</span>
              <span className={`${styles.detailValue} ${styles.monospaceValue}`}>
                {String(selectedNode.data?.originalId || selectedNode.id)}
              </span>
            </div>
            {Object.entries(selectedNode.data || {})
              .filter(([k]) => !['label', 'type', 'originalId', 'originalIndex'].includes(k))
              .slice(0, 8)
              .map(([k, v]) => (
                <div key={k} className={styles.detailRow}>
                  <span className={styles.detailLabel}>{k}</span>
                  <span className={`${styles.detailValue} ${styles.monospaceValue}`}>
                    {typeof v === 'object' ? JSON.stringify(v).slice(0, 80) : String(v).slice(0, 80)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className={`${styles.legend} ${darkMode ? styles.darkLegend : ''}`}>
        <div className={styles.graphStats}>
          <span>{graphStats.visibleNodeCount} nodes</span>
          <span>{graphStats.visibleEdgeCount} edges</span>
          <span>{graphStats.communityCount} groups</span>
          <span>{(graphStats.density * 100).toFixed(1)}% dense</span>
          {graphStats.hub && graphStats.hub[1] > 0 && (
            <span title="Most connected visible node">
              hub {graphStats.hub[0]} ({graphStats.hub[1]})
            </span>
          )}
        </div>
        {Array.from(allTypes)
          .sort()
          .map((t) => (
            <div key={t} className={styles.legendItem}>
              <span
                className={`${styles.legendDot} ${getTypeClass(t)}`}
              />
              <span className={styles.legendText}>{t}</span>
            </div>
          ))}
      </div>
    </div>
  )
}
