import { useState } from 'react'
import { UARPanel } from './components/UARPanel'
import { UARSimplePanel } from './components/UARSimplePanel'
import styles from './App.module.css'

const MODE_KEY = 'uar.ui.mode'

export default function App() {
  const [advanced, setAdvanced] = useState(() => {
    try {
      const saved = localStorage.getItem(MODE_KEY)
      return saved === null || saved === 'advanced'
    } catch {
      return true
    }
  })

  const toggleMode = () => {
    const next = !advanced
    setAdvanced(next)
    try {
      localStorage.setItem(MODE_KEY, next ? 'advanced' : 'simple')
    } catch {
      // ignore
    }
  }

  return (
    <div className={styles.container}>
      {advanced ? (
        <UARPanel onToggleMode={toggleMode} modeLabel="Simple" />
      ) : (
        <UARSimplePanel onToggleMode={toggleMode} modeLabel="Advanced" />
      )}
    </div>
  )
}
