import { useState, useCallback } from 'react'
import styles from './RiscvVisualizer.module.css'

interface Register {
  index: number
  name: string
  value: number
  hex: string
}

interface MemoryCell {
  addr: number
  hex: string
}

interface TraceEntry {
  pc: number
  instr: string
  opcode: string
  rd: number | null
  rs1: number
  rs2: number
  registers: number[]
}

interface RiscvData {
  registers: Register[]
  memory: MemoryCell[]
  trace: TraceEntry[]
  instruction_count: number
  final_pc: number
}

interface RiscvVisualizerProps {
  data: RiscvData | null
  darkMode?: boolean
}

export function RiscvVisualizer({ data, darkMode = false }: RiscvVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'registers' | 'memory' | 'trace'>('registers')
  const [copyFlash, setCopyFlash] = useState(false)

  const handleCopy = useCallback(() => {
    if (!data) return
    navigator.clipboard.writeText(JSON.stringify(data, null, 2)).catch(() => {})
    setCopyFlash(true)
    setTimeout(() => setCopyFlash(false), 1000)
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the riscv_sim skill to generate execution data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          RISC-V ({data.instruction_count} instr, PC=0x{data.final_pc.toString(16)})
        </span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.tabButton} ${activeTab === 'registers' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('registers')}
          >
            Registers
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'memory' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('memory')}
          >
            Memory
          </button>
          <button
            className={`${styles.tabButton} ${activeTab === 'trace' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('trace')}
          >
            Trace
          </button>
          <button className={styles.toolbarButton} onClick={handleCopy}>
            {copyFlash ? '✅' : '📋'}
          </button>
        </div>
      </div>

      {activeTab === 'registers' && (
        <div className={styles.scrollContent}>
          <div className={styles.registerGrid}>
            {data.registers.map((reg) => (
              <div
                key={reg.index}
                className={`${styles.registerCell} ${reg.index === 0 ? styles.registerZero : ''}`}
              >
                <div className={styles.regName}>
                  x{reg.index} ({reg.name})
                </div>
                <div className={styles.regValue}>{reg.hex}</div>
                <div className={styles.regDec}>{reg.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'memory' && (
        <div className={styles.scrollContent}>
          <div className={styles.memoryTable}>
            <div className={styles.memHeader}>
              <span>Address</span>
              <span>Value</span>
              <span>+1</span>
              <span>+2</span>
              <span>+3</span>
            </div>
            {data.memory.map((cell) => {
              const bytes = cell.hex.slice(2).match(/.{2}/g) || []
              return (
                <div key={cell.addr} className={styles.memRow}>
                  <span className={styles.memAddr}>0x{cell.addr.toString(16).padStart(4, '0')}</span>
                  {bytes.map((b, i) => (
                    <span key={i} className={styles.memByte}>{b}</span>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {activeTab === 'trace' && (
        <div className={styles.scrollContent}>
          <div className={styles.traceTable}>
            <div className={styles.traceHeader}>
              <span>#</span>
              <span>PC</span>
              <span>Instruction</span>
              <span>Opcode</span>
              <span>RD</span>
            </div>
            {data.trace.map((entry, i) => (
              <div key={i} className={styles.traceRow}>
                <span className={styles.traceIdx}>{i + 1}</span>
                <span className={styles.tracePc}>0x{entry.pc.toString(16)}</span>
                <span className={styles.traceInstr}>{entry.instr}</span>
                <span className={styles.traceOp}>{entry.opcode}</span>
                <span className={styles.traceRd}>
                  {entry.rd !== null ? `x${entry.rd}` : '-'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
