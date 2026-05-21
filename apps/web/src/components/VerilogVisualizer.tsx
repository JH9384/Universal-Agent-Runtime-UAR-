import { useState } from 'react'
import styles from './VerilogVisualizer.module.css'

interface ModuleDef {
  name: string
  ports: { name: string; direction: string; width: string }[]
  signals: { name: string; type: string; width: string }[]
  instances: { module: string; instance: string; connections: { port: string; signal: string }[] }[]
  assigns: { lhs: string; rhs: string }[]
}

interface HierarchyNode {
  module: string
  children: { type: string; module: string; name: string }[]
}

interface VerilogData {
  modules: ModuleDef[]
  hierarchy: HierarchyNode[]
  module_count: number
  total_ports: number
  total_signals: number
  total_instances: number
}

interface VerilogVisualizerProps {
  data: VerilogData | null
  darkMode?: boolean
}

export function VerilogVisualizer({ data, darkMode = false }: VerilogVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'modules' | 'hierarchy' | 'signals'>('modules')
  const [expandedModule, setExpandedModule] = useState<string | null>(null)

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the verilog_parse skill to generate module data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          Verilog ({data.module_count} modules, {data.total_instances} instances)
        </span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'modules' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('modules')}
          >
            Modules
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'hierarchy' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('hierarchy')}
          >
            Hierarchy
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'signals' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('signals')}
          >
            Signals
          </button>
        </div>
      </div>

      {activeTab === 'modules' && (
        <div className={styles.scrollContent}>
          {data.modules.map((mod) => (
            <div key={mod.name} className={styles.moduleCard}>
              <div
                className={styles.moduleHeader}
                onClick={() => setExpandedModule(
                  expandedModule === mod.name ? null : mod.name
                )}
              >
                <span className={styles.moduleName}>{mod.name}</span>
                <span className={styles.moduleStats}>
                  {mod.ports.length}P / {mod.signals.length}S / {mod.instances.length}I
                </span>
              </div>
              {expandedModule === mod.name && (
                <div className={styles.moduleBody}>
                  {mod.ports.length > 0 && (
                    <div className={styles.subSection}>
                      <h5 className={styles.subTitle}>Ports</h5>
                      {mod.ports.map((p) => (
                        <div key={p.name} className={styles.portRow}>
                          <span className={styles[p.direction] || styles.portName}>
                            {p.direction}
                          </span>
                          <span className={styles.portName}>{p.name}</span>
                          <span className={styles.portWidth}>{p.width}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {mod.instances.length > 0 && (
                    <div className={styles.subSection}>
                      <h5 className={styles.subTitle}>Instances</h5>
                      {mod.instances.map((inst) => (
                        <div key={inst.instance} className={styles.instRow}>
                          <span className={styles.instMod}>{inst.module}</span>
                          <span className={styles.instName}>{inst.instance}</span>
                          <span className={styles.instConns}>
                            {inst.connections.length} conns
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {mod.assigns.length > 0 && (
                    <div className={styles.subSection}>
                      <h5 className={styles.subTitle}>Assignments</h5>
                      {mod.assigns.map((a, i) => (
                        <div key={i} className={styles.assignRow}>
                          <span className={styles.assignLhs}>{a.lhs}</span>
                          <span>=</span>
                          <span className={styles.assignRhs}>{a.rhs}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'hierarchy' && (
        <div className={styles.scrollContent}>
          {data.hierarchy.map((node) => (
            <div key={node.module} className={styles.hierarchyTree}>
              <div className={styles.treeRoot}>{node.module}</div>
              {node.children.length > 0 && (
                <div className={styles.treeChildren}>
                  {node.children.map((child) => (
                    <div key={child.name} className={styles.treeChild}>
                      <span className={styles.treeMod}>{child.module}</span>
                      <span className={styles.treeInst}>{child.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'signals' && (
        <div className={styles.scrollContent}>
          <div className={styles.signalTable}>
            <div className={styles.sigHeader}>
              <span>Module</span>
              <span>Name</span>
              <span>Type</span>
              <span>Width</span>
            </div>
            {data.modules.map((mod) =>
              mod.signals.map((sig) => (
                <div key={`${mod.name}-${sig.name}`} className={styles.sigRow}>
                  <span className={styles.sigMod}>{mod.name}</span>
                  <span className={styles.sigName}>{sig.name}</span>
                  <span className={styles.sigType}>{sig.type}</span>
                  <span className={styles.sigWidth}>{sig.width}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
