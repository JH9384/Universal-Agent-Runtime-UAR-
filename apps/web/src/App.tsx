import { useState } from 'react'
import { UARPanel } from './components/UARPanel'
import { UARSimplePanel } from './components/UARSimplePanel'
import styles from './App.module.css'

const MODE_KEY = 'uar.ui.mode'

export default function App() {
  const [advanced, setAdvanced] = useState(() => {
    try {
      return localStorage.getItem(MODE_KEY) === 'advanced'
    } catch {
      return false
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
        <UARPanel />
      ) : (
        <UARSimplePanel />
      )}
      <button
        type="button"
        className={styles.modeToggle}
        onClick={toggleMode}
        aria-label={advanced ? 'Switch to simple mode' : 'Switch to advanced mode'}
      >
        {advanced ? 'Simple' : 'Advanced'}
      </button>
    </div>
  )
}
