import { useCallback, useEffect, useState } from 'react'
import styles from './UARPanel.module.css'

const COLLAPSE_KEY = 'uar.collapsedSections'

function readCollapsed(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(COLLAPSE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function writeCollapsed(state: Record<string, boolean>) {
  try {
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(state))
  } catch {
    // ignore
  }
}

interface CollapsibleSectionProps {
  id: string
  title: string
  info?: string
  children: React.ReactNode
  defaultOpen?: boolean
  headerActions?: React.ReactNode
}

export default function CollapsibleSection({
  id,
  title,
  info,
  children,
  defaultOpen = true,
  headerActions,
}: CollapsibleSectionProps) {
  const [collapsed, setCollapsed] = useState(() => readCollapsed()[id] ?? !defaultOpen)

  useEffect(() => {
    const onToggle = () => {
      setCollapsed(readCollapsed()[id] ?? !defaultOpen)
    }
    window.addEventListener('uar:collapse-toggle', onToggle)
    return () => window.removeEventListener('uar:collapse-toggle', onToggle)
  }, [id, defaultOpen])

  const toggle = useCallback(() => {
    const state = readCollapsed()
    state[id] = !state[id]
    writeCollapsed(state)
    window.dispatchEvent(new Event('uar:collapse-toggle'))
  }, [id])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        toggle()
      }
    },
    [toggle]
  )

  return (
    <div className={styles.collapsibleBox}>
      <div
        className={styles.collapsibleHeader}
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={onKeyDown}
        aria-expanded={!collapsed}
        aria-controls={`section-${id}`}
      >
        <strong className={styles.collapsibleTitle}>{title}</strong>
        {info && <span className={styles.collapsibleInfo}>{info}</span>}
        {headerActions}
        <span className={styles.collapsibleIcon}>
          {collapsed ? '▶' : '▼'}
        </span>
      </div>
      {!collapsed && (
        <div id={`section-${id}`} className={styles.collapsibleContent}>
          {children}
        </div>
      )}
    </div>
  )
}
